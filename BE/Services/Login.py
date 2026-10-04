from Repositories.AuthRepository import AuthRepository

auth_repository = AuthRepository()


def login_user(login, password):
    if login == "" or password == "":
        return None

    user = auth_repository.get_user_by_username_or_email(login)

    if user is None:
        return None

    if user.hashPassword == password:
        return user
    else:
        return None
