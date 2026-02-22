# ==============================================================================
# main.py   –  REX 4.0   Main Entry Point
# ==============================================================================
# Design
#   • Single-threaded event loop: listen → classify → execute → speak → repeat.
#   • Startup sequence:
#       1. Load config
#       2. Authenticate user (retry on failure)
#       3. Calibrate microphone
#       4. Start proactive engine
#       5. Enter main loop
#   • Shutdown sequence:
#       1. Stop proactive engine
#       2. Save all state (config, history, memory)
#       3. Close audio streams
#       4. Log final stats
#   • Graceful exit on Ctrl+C or "exit rex" command.
# ==============================================================================

from __future__ import annotations

import signal
import sys
import time
from datetime import datetime

# Core
from core.config   import get_config
from core.logger   import get_logger, LogCategory
from core.auth     import get_auth, Permission
from core.speech   import SpeechEngine, Priority
from core.listener_hybrid import HybridVoiceListener as VoiceListener
from core.intent   import IntentClassifier, IntentType

# Commands
from commands.handler import CommandRouter

# Intelligence
from intelligence.conversation   import ConversationManager
from intelligence.proactive      import ProactiveEngine
from intelligence.history        import CommandHistory
from intelligence.context_memory import ContextMemory


# ─── Globals ──────────────────────────────────────────────────────────────────

_RUNNING = True


def _signal_handler(sig, frame):
    global _RUNNING
    _RUNNING = False


# ─── Startup ──────────────────────────────────────────────────────────────────


def startup() -> tuple:
    """
    Initialise all subsystems and authenticate the user.

    Returns (session_token, username, components_dict).
    """
    print("\n" + "=" * 70)
    print("  REX 4.0  –  Intelligent Voice Assistant")
    print("=" * 70 + "\n")

    # ── config & logging ──
    config = get_config()
    logger = get_logger()
    logger.info(LogCategory.SYSTEM, "REX 4.0 starting up")
    
    # Check for verbose/debug mode
    verbose_mode = config.ui.verbosity in ("verbose", "debug")

    # validate config
    errors = config.validate()
    if errors:
        print("⚠️  Configuration errors detected:")
        for err in errors:
            print(f"   • {err}")
        if any("model" in e.lower() for e in errors):
            print("\nFatal: Vosk model not found. Please download it and set recognition.model_path.")
            sys.exit(1)
        print("\nContinuing with warnings...\n")

    # ── authentication ──
    auth = get_auth()
    session_token = None
    username      = None

    print("🔐 Authentication required\n")
    for attempt in range(3):
        un = input("Username: ").strip()
        pw = input("Password: ").strip()
        success, token, error = auth.authenticate(un, pw)
        if success:
            session_token = token
            username      = un
            print(f"\n✓ Welcome, {username}!\n")
            if verbose_mode:
                print(f"[DEBUG] Session token: {token[:16]}...")
                print(f"[DEBUG] Role: {auth.validate_session(token)[1].role.value}")
            break
        print(f"✗ {error}\n")
    else:
        print("Authentication failed. Exiting.")
        sys.exit(1)

    # ── TTS ──
    print("🔊 Initialising speech engine...")
    speech = SpeechEngine()
    speech.speak("Hello! REX is starting up.", Priority.HIGH)

    # ── voice listener ──
    print("🎤 Initialising voice recognition...")
    listener = VoiceListener(speaking_check=speech.is_speaking)

    print("   Calibrating microphone... (stay quiet for 2 seconds)")
    threshold = listener.calibrate(duration=2.0)
    print(f"   ✓ Calibrated: threshold = {threshold:.1f}\n")
    if verbose_mode:
        print(f"[DEBUG] Sample rate: {config.audio.sample_rate} Hz")
        print(f"[DEBUG] Block size: {config.audio.block_size} frames")
        print(f"[DEBUG] Energy threshold: {threshold:.1f}\n")

    # ── intent classifier ──
    classifier = IntentClassifier()
    if verbose_mode:
        stats = classifier.get_stats()
        print(f"[DEBUG] Intent classifier loaded: {stats['corrections']} learned corrections\n")

    # ── command router ──
    router = CommandRouter()

    # ── intelligence ──
    conversation = ConversationManager()
    history      = CommandHistory()

    # ── proactive engine ──
    proactive = ProactiveEngine(speech_callback=speech.speak_urgent)
    if config.features.proactive_suggestions:
        proactive.start()

    speech.speak("REX is ready. How can I help you?", Priority.HIGH)
    print("=" * 70)
    if verbose_mode:
        print("  REX is listening in VERBOSE mode...")
        print("  You will see detailed recognition & classification info")
    else:
        print("  REX is listening... (Say 'exit REX' or press Ctrl+C to quit)")
    print("=" * 70 + "\n")

    return session_token, username, {
        "config":       config,
        "logger":       logger,
        "auth":         auth,
        "speech":       speech,
        "listener":     listener,
        "classifier":   classifier,
        "router":       router,
        "conversation": conversation,
        "history":      history,
        "proactive":    proactive,
    }


# ─── Main loop ────────────────────────────────────────────────────────────────


def main_loop(session_token: str, username: str, components: dict) -> None:
    """
    Core event loop: listen → classify → execute → speak → repeat.
    """
    global _RUNNING

    config       = components["config"]
    logger       = components["logger"]
    speech       = components["speech"]
    listener     = components["listener"]
    classifier   = components["classifier"]
    router       = components["router"]
    conversation = components["conversation"]
    history      = components["history"]
    proactive    = components["proactive"]
    
    verbose_mode = config.ui.verbosity in ("verbose", "debug")

    while _RUNNING:
        try:
            # ── listen ────────────────────────────────────────────────────
            print("\n[Listening...]", end=" ", flush=True)
            
            if verbose_mode:
                print(f"\n[DEBUG] Queue size: {listener._audio_q.qsize()}, Energy threshold: {listener._energy_threshold:.1f}")
            
            result = listener.listen(timeout=30.0, phrase_timeout=3.0)

            if result is None:
                # timeout – silent loop
                if verbose_mode:
                    print("[DEBUG] Timeout - no speech detected")
                continue

            user_text = result.text
            
            # Display what was heard
            if verbose_mode:
                print(f"\n{'─' * 70}")
                print(f"🎤 HEARD: \"{user_text}\"")
                print(f"   Confidence: {result.confidence:.2%}")
                if result.alternatives:
                    print(f"   Alternatives: {', '.join(result.alternatives[:3])}")
            else:
                print(f"You said: \"{user_text}\"")

            # mark interaction for proactive engine
            proactive.mark_interaction()

            # ── classify ──────────────────────────────────────────────────
            intent_result = classifier.classify(user_text)
            intent        = intent_result.intent

            if verbose_mode:
                print(f"\n🧠 CLASSIFIED:")
                print(f"   Intent: {intent.value}")
                print(f"   Confidence: {intent_result.confidence:.2%}")
                if intent_result.parameters:
                    print(f"   Parameters:")
                    for k, v in intent_result.parameters.items():
                        print(f"      • {k}: {v}")
                if intent_result.alternatives:
                    print(f"   Alternative intents:")
                    for alt, conf in intent_result.alternatives[:3]:
                        print(f"      • {alt.value} ({conf:.2%})")

            # log
            conversation.add_turn("user", user_text, intent.value)
            logger.info(LogCategory.INTENT,
                        f"Classified: {intent.value} (conf={intent_result.confidence:.2f})")

            # ── handle clarifications (YES / NO / CANCEL) ─────────────────
            if intent in (IntentType.YES, IntentType.NO, IntentType.CANCEL):
                if conversation.has_pending():
                    verdict  = intent.value
                    response = conversation.resolve_pending(verdict)
                    speech.speak(response, Priority.NORMAL)
                    conversation.add_turn("assistant", response, intent.value)
                    
                    if verbose_mode:
                        print(f"\n💬 RESPONSE: \"{response}\"")
                    continue
                else:
                    speech.speak("I wasn't expecting a yes or no right now. What would you like me to do?")
                    continue

            # ── unknown intent ────────────────────────────────────────────
            if intent == IntentType.UNKNOWN:
                response = "I didn't understand that. Could you rephrase?"
                speech.speak(response, Priority.NORMAL)
                conversation.add_turn("assistant", response, "unknown")
                
                if verbose_mode:
                    print(f"\n❌ UNKNOWN INTENT")
                    print(f"💬 RESPONSE: \"{response}\"")
                continue

            # ── farewell (exit) ───────────────────────────────────────────
            if intent == IntentType.FAREWELL:
                cmd_result = router.execute(intent_result, session_token)
                speech.speak(cmd_result.message, Priority.HIGH)
                speech.wait_until_done(timeout=5)
                conversation.add_turn("assistant", cmd_result.message, intent.value)
                # user wants to exit
                _RUNNING = False
                break

            # ── route & execute ───────────────────────────────────────────
            if verbose_mode:
                print(f"\n⚙️  EXECUTING: {intent.value}")
                start = time.time()
            
            cmd_result = router.execute(intent_result, session_token)
            
            if verbose_mode:
                elapsed = time.time() - start
                print(f"   Duration: {elapsed:.3f}s")
                print(f"   Success: {'✓' if cmd_result.success else '✗'}")
                if cmd_result.error:
                    print(f"   Error: {cmd_result.error}")

            # speak result
            if cmd_result.success:
                speech.speak(cmd_result.message, Priority.NORMAL)
            else:
                speech.speak(cmd_result.message, Priority.HIGH)
            
            if verbose_mode:
                print(f"\n💬 RESPONSE: \"{cmd_result.message}\"")
                print(f"{'─' * 70}")

            # log to conversation & history
            conversation.add_turn("assistant", cmd_result.message, intent.value)
            history.add(
                intent=intent.value,
                raw_text=user_text,
                success=cmd_result.success,
                message=cmd_result.message,
                duration=cmd_result.duration,
                username=username,
                error=cmd_result.error or "",
            )

            # ── post-command actions ──────────────────────────────────────
            # If the command returned a special action (e.g. os_shutdown)
            # we handle it here in the main loop so we can cleanly exit.

            action = cmd_result.data.get("action")
            if action == "os_shutdown":
                print("\n🔴 Shutting down computer...")
                speech.wait_until_done(timeout=5)
                _RUNNING = False
                # The actual OS shutdown would go here:
                # import os; os.system("shutdown /s /t 0")  # Windows
                # For safety we don't actually execute it in this demo.
                break

            elif action == "os_restart":
                print("\n🔄 Restarting computer...")
                speech.wait_until_done(timeout=5)
                _RUNNING = False
                # os.system("shutdown /r /t 0")
                break

            elif action == "os_sleep":
                print("\n💤 Putting computer to sleep...")
                speech.wait_until_done(timeout=5)
                # os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                pass

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user (Ctrl+C)")
            _RUNNING = False
            break

        except Exception as exc:
            logger.error(LogCategory.ERROR, f"Main loop exception: {exc}")
            if verbose_mode:
                import traceback
                print(f"\n❌ ERROR: {exc}")
                traceback.print_exc()
            speech.speak("An error occurred. Please try again.", Priority.HIGH)


# ─── Shutdown ─────────────────────────────────────────────────────────────────


def shutdown(components: dict) -> None:
    """
    Clean shutdown: stop threads, close streams, save state, log stats.
    """
    print("\n" + "=" * 70)
    print("  Shutting down REX...")
    print("=" * 70 + "\n")

    logger     = components["logger"]
    speech     = components["speech"]
    listener   = components["listener"]
    history    = components["history"]
    proactive  = components["proactive"]

    # ── stop proactive engine ──
    print("  • Stopping proactive engine...")
    proactive.stop()

    # ── final speech ──
    speech.speak("Goodbye! REX is shutting down.", Priority.URGENT)
    speech.wait_until_done(timeout=5)

    # ── close audio ──
    print("  • Closing audio streams...")
    listener.shutdown()
    speech.shutdown()

    # ── stats ──
    print("\n📊 Session Statistics:")
    h_stats = history.stats()
    print(f"   Commands executed:  {h_stats['total']}")
    print(f"   Successful:         {h_stats['successful']}")
    print(f"   Failed:             {h_stats['failed']}")
    print(f"   Avg duration:       {h_stats['avg_duration']:.3f}s")

    l_stats = listener.get_stats()
    print(f"\n   Voice recognised:   {l_stats['total_recognised']}")
    print(f"   Recognition errors: {l_stats['errors']}")

    s_stats = speech.get_stats()
    print(f"\n   Messages spoken:    {s_stats['total_spoken']}")
    print(f"   TTS errors:         {s_stats['errors']}")

    # ── final log ──
    logger.info(LogCategory.SYSTEM, "REX 4.0 shutdown complete", h_stats)
    logger.close()

    print("\n" + "=" * 70)
    print("  REX 4.0 shut down cleanly. Goodbye!")
    print("=" * 70 + "\n")


# ─── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Main entry point."""
    # register signal handler for graceful Ctrl+C
    signal.signal(signal.SIGINT, _signal_handler)

    try:
        session_token, username, components = startup()
        main_loop(session_token, username, components)
    finally:
        # shutdown is called even if startup() fails partway
        if "components" in locals():
            shutdown(components)


if __name__ == "__main__":
    main()