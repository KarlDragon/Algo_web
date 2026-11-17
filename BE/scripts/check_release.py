"""Non-destructive pre-release audit; never prints secrets.

From BE: py scripts/check_release.py [--production]
"""
import argparse
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')


def audit(production=False):
    errors=[]
    warnings=[]
    notes=[]
    get=lambda name:os.getenv(name,'').strip()
    secret=get('JWT_SECRET_KEY')
    if not secret or len(secret)<32 or any(x in secret.upper() for x in ('REPLACE', 'SECRET_RIENG', 'PASSWORD', 'CHANGE_ME')):
        errors.append('JWT_SECRET_KEY: cần khóa ngẫu nhiên riêng, dài ít nhất 32 ký tự.')
    if get('JWT_ALGORITHM') and get('JWT_ALGORITHM')!='HS256':
        errors.append('JWT_ALGORITHM: dự án chỉ hỗ trợ HS256.')
    if not get('DATABASE_URL'):
        errors.append('Thiếu DATABASE_URL trong .env.')
    if not (ROOT/'alembic.ini').exists():
        errors.append('Không tìm thấy alembic.ini.')
    if not (ROOT/'tests'/'test_auth.py').exists():
        errors.append('Không tìm thấy bộ test Auth.')
    if get('SQLALCHEMY_ECHO').lower() in ('true','yes','1'):
        warnings.append('SQLALCHEMY_ECHO đang bật, có thể log thông tin SQL.')

    smtp_fields=['SMTP_HOST','SMTP_FROM','SMTP_USERNAME','SMTP_PASSWORD']
    smtp_on=all(get(s) for s in smtp_fields)
    if not smtp_on:
        warnings.append('SMTP chưa đầy đủ; chưa gửi email thật được.')
    if not get('FRONTEND_RESET_PASSWORD_URL'):
        warnings.append('Thiếu FRONTEND_RESET_PASSWORD_URL; email reset sẽ không được gửi.')
    if get('SMTP_HOST').lower()=='sandbox.smtp.mailtrap.io':
        warnings.append('Mailtrap Sandbox chỉ giữ thư thử nghiệm, KHÔNG chuyển thư đến inbox người dùng.')

    if production:
        if not get('REDIS_URL'):
            errors.append('Thiếu REDIS_URL cho cache/rate limit nhiều worker.')
        if not get('TRUSTED_HOSTS'):
            errors.append('Thiếu TRUSTED_HOSTS cho reverse proxy/host whitelist.')
        if not get('CORS_ORIGINS') or '*' in get('CORS_ORIGINS'):
            errors.append('CORS_ORIGINS phải cấu hình origin FE thật, không được wildcard.')
        if get('SMTP_HOST')=='sandbox.smtp.mailtrap.io' or not smtp_on:
            errors.append('Production phải dùng SMTP gửi thư thật, không dùng Mailtrap Sandbox.')
        if not get('FRONTEND_RESET_PASSWORD_URL').startswith('https://'):
            errors.append('FRONTEND_RESET_PASSWORD_URL phải là HTTPS khi deploy.')
        if get('DATABASE_URL').lower().startswith('sqlite:'):
            warnings.append('SQLite có thể hạn chế write concurrency ở production; cân nhắc PostgreSQL.')
        if get('FORCE_HTTPS').lower() not in ('true','1'):
            warnings.append('Hãy bắt buộc HTTPS tại reverse proxy (hoặc FORCE_HTTPS=true nếu proxy đúng).')
    else:
        notes.append('Đây là rà soát cấu hình local, KHÔNG xác nhận hệ thống chạy production an toàn.')

    for prefix,arr in [('LỖI',errors),('CẦN XỬ LÝ',warnings),('GHI CHÚ',notes)]:
        for line in arr:
            print(f'[{prefix}] {line}')
    print(f'Tổng kết: {len(errors)} lỗi bắt buộc, {len(warnings)} cảnh báo.')
    return 1 if errors else 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Kiểm tra cấu hình phát hành BE Algo_web')
    parser.add_argument('--production',action='store_true',help='Chặn phát hành nếu thiếu cấu hình production')
    args=parser.parse_args()
    sys.exit(audit(args.production))
