# -*- coding: utf-8 -*-
# 分块续传：每块 8MB，服务器已有部分自动跳过（断点续传）
import paramiko, os, time

def upload_resume(sftp, src, dst):
    local = os.path.getsize(src)
    try:
        remote = sftp.stat(dst).st_size
    except Exception:
        remote = 0
    if remote >= local:
        print(f"[跳过] {os.path.basename(src)} 已完整({local/1048576:.0f}MB)")
        return True
    print(f"[上传] {os.path.basename(src)} 本地 {local/1048576:.0f}MB，已传 {remote/1048576:.0f}MB，续传中...", flush=True)
    done = remote
    with open(src, 'rb') as f:
        f.seek(remote)
        mode = 'r+b' if remote > 0 else 'wb'  # 已有部分续写，否则新建
        with sftp.open(dst, mode) as rf:
            if remote > 0:
                rf.seek(remote)
            while True:
                chunk = f.read(8 * 1024 * 1024)
                if not chunk:
                    break
                rf.write(chunk)
                rf.flush()
                done += len(chunk)
                pct = done * 100 // local
                print(f"   {done/1048576:.0f}/{local/1048576:.0f} MB ({pct}%)", flush=True)
    sz = sftp.stat(dst).st_size
    ok = sz == local
    print(f"[完成] {os.path.basename(src)} {sz/1048576:.0f}MB {'✔ 大小匹配' if ok else f'✘ 不匹配({sz} != {local})'}", flush=True)
    return ok

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("182.254.209.123", username="root", password="ybwlz..0426", timeout=30)
c.get_transport().set_keepalive(30)
sftp = c.open_sftp()

files = [
    ("C:/Users/50534/Desktop/桌面整理/文件夹归档/项目代码/document/documentplatform/doctmanage/release/zhiyu-win32-x64.zip",
     "/www/wwwroot/zhiyu/downloads/zhiyu-win32-x64.zip"),
    ("C:/Users/50534/Desktop/桌面整理/文件夹归档/项目代码/document/documentplatform/doctmanage/installer/dist-single/知屿安装器.exe",
     "/www/wwwroot/zhiyu/downloads/知屿安装器.exe"),
]
allok = True
for src, dst in files:
    if not os.path.exists(src):
        print("[缺失]", src)
        allok = False
        continue
    try:
        if not upload_resume(sftp, src, dst):
            allok = False
    except Exception as e:
        print("[中断]", os.path.basename(src), repr(e), "稍后重跑本脚本即可续传", flush=True)
        allok = False
        break
sftp.close()
print("==========")
print("全部完成 ✔" if allok else "部分未完成，重跑本脚本可断点续传")
c.close()
