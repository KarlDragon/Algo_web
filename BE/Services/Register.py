import re
from pwdlib import PasswordHash

from Repositories.AuthRepository import (
    create_user_table,
    add_user,
    get_user_by_username,
    get_user_by_email
)

password_hash = PasswordHash.recommended()


def check_username(username):
    # Username khong duoc rong
    if username == "":
        print("Username khong duoc rong!")
        return False

    # Username phai co chu
    if not re.search(r"[A-Za-z]", username):
        print("Username phai co it nhat 1 chu cai!")
        return False

    # Username phai co so
    if not re.search(r"[0-9]", username):
        print("Username phai co it nhat 1 chu so!")
        return False

    return True
    # Username khong duoc qua 50 ky tu
    if len(username) > 50:
        print("Username khong duoc qua 50 ky tu!")
        return False

def check_password(password):
    # Khong duoc rong
    if password == "":
        print("Password khong duoc rong!")
        return False

    # Toi thieu 8 ky tu
    if len(password) < 8:
        print("Password phai co it nhat 8 ky tu!")
        return False

    # Khong qua 64 ky tu
    if len(password) > 64:
        print("Password khong duoc qua 64 ky tu!")
        return False

    # Phai co chu in hoa
    if not re.search(r"[A-Z]", password):
        print("Password phai co it nhat 1 chu cai in hoa!")
        return False

    # Phai co so
    if not re.search(r"[0-9]", password):
        print("Password phai co it nhat 1 chu so!")
        return False

    # Phai co ky tu dac biet
    if not re.search(r"[^A-Za-z0-9]", password):
        print("Password phai co it nhat 1 ky tu dac biet!")
        return False

    return True


def check_email(email):
    # Email khong duoc rong
    if email == "":
        print("Email khong duoc rong!")
        return False

    # Email khong duoc qua 100 ky tu
    if len(email) > 100:
        print("Email khong duoc qua 100 ky tu!")
        return False

    # Kiem tra dinh dang email
    email_pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    if not re.match(email_pattern, email):
        print("Email khong hop le!")
        return False

    return True

def hash_password(password):
    return password_hash.hash(password)

def register_user(username, password, email):

    # Kiem tra username
    if not check_username(username):
        return None

    # Kiem tra password
    if not check_password(password):
        return None

    # Kiem tra email
    if not check_email(email):
        return None

    # Tao bang users neu chua ton tai
    create_user_table()

    # Kiem tra username da ton tai chua
    existing_username = get_user_by_username(username)

    if existing_username is not None:
        print("Username da ton tai!")
        return None

    # Kiem tra email da ton tai chua
    existing_email = get_user_by_email(email)

    if existing_email is not None:
        print("Email da ton tai!")
        return None

    # Hash password
    hashed_password = hash_password(password)

    # Them user vao database
    user = add_user(
        username,
        hashed_password,
        email
    )

    return user

# PHẦN NÀY TUI BỔ SUNG THÊM CÁI CHECK EMAIL VÀ HASH PASSWORD !!!!!