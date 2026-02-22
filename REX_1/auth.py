def authenticate():
    name = input("Enter username: ")
    code = input("Enter code: ")

    if code == "20":
        print("Access granted")
        return name, "admin"
    else:
        print("Access denied")
        return None, None
