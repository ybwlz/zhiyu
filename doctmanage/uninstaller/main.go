// 知屿卸载器：系统标准对话框，轻量 2MB，稳定可用
package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

var user32 = syscall.NewLazyDLL("user32.dll")
var procMessageBox = user32.NewProc("MessageBoxW")

const (
	MB_OK              = 0x0000
	MB_YESNO           = 0x0004
	MB_ICONQUESTION    = 0x0020
	MB_ICONINFORMATION = 0x0040
	MB_DEFBUTTON2      = 0x0100
	IDYES              = 6
)

func msgBox(title, text string, flags uintptr) int {
	r, _, _ := procMessageBox.Call(
		0,
		uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr(text))),
		uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr(title))),
		flags,
	)
	return int(r)
}

// 从注册表读安装目录
func readInstallRoot() string {
	keys := []string{
		`HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿`,
		`HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿`,
	}
	for _, k := range keys {
		out, err := exec.Command("reg", "query", k, "/v", "InstallLocation").Output()
		if err != nil {
			continue
		}
		lines := strings.Split(string(out), "\r\n")
		for _, l := range lines {
			if strings.Contains(l, "InstallLocation") {
				if idx := strings.Index(l, "REG_SZ"); idx >= 0 {
					v := strings.TrimSpace(l[idx+6:])
					if v != "" {
						return v
					}
				}
			}
		}
	}
	return ""
}

func main() {
	root := readInstallRoot()
	if root == "" {
		root = "D:\\Software\\知屿"
	}

	// 先结束主程序
	exec.Command("taskkill", "/f", "/im", "知屿.exe").Run()
	time.Sleep(500 * time.Millisecond)

	r := msgBox("卸载知屿",
		"确定要卸载知屿吗？\n\n将删除程序文件、桌面快捷方式与开机自启项。\n你的云端笔记数据不受影响（保存在服务器）。",
		MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2)
	if r != IDYES {
		return
	}

	// 结束主程序（再次确保）
	exec.Command("taskkill", "/f", "/im", "知屿.exe").Run()

	// 删除桌面快捷方式（用户桌面 + 公共桌面）
	for _, dir := range []string{os.Getenv("USERPROFILE") + `\Desktop`, `C:\Users\Public\Desktop`} {
		os.Remove(filepath.Join(dir, "知屿.lnk"))
	}

	// 删除注册表卸载项 + 开机自启
	exec.Command("reg", "delete", `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿`, "/f").Run()
	exec.Command("reg", "delete", `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿`, "/f").Run()
	exec.Command("reg", "delete", `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, "/v", "知屿", "/f").Run()

	// 后台延迟删除整个安装目录（含卸载器自身），等本进程退出后执行
	ps := fmt.Sprintf("Start-Sleep -Seconds 2; Remove-Item -LiteralPath '%s' -Recurse -Force -ErrorAction SilentlyContinue", root)
	cmd := exec.Command("powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	cmd.Start()

	msgBox("卸载完成", "知屿 已卸载完成。", MB_OK|MB_ICONINFORMATION)
}
