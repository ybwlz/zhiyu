// 知屿卸载器：系统标准对话框 + 可靠自删除（复制副本到临时目录 → 原进程退出 → 副本删整个目录）
package main

import (
	"fmt"
	"io"
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

// 静默执行命令（不弹控制台窗口）
func silent(name string, args ...string) {
	cmd := exec.Command(name, args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	cmd.Run()
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, in)
	return err
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
		for _, l := range strings.Split(string(out), "\r\n") {
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

// --cleanup 模式：临时副本——延迟删除整个安装目录（原进程已退出），再删自己
func cleanup(root string) {
	time.Sleep(2000 * time.Millisecond)
	os.RemoveAll(root)
	// 删除临时副本自己（PowerShell 隐藏执行，路径为 ASCII）
	ps := "Start-Sleep -Seconds 1; Remove-Item -LiteralPath '" + os.Args[0] + "' -Force -ErrorAction SilentlyContinue"
	cmd := exec.Command("powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	cmd.Start()
}

func main() {
	if len(os.Args) > 1 && os.Args[1] == "--cleanup" {
		root := ""
		if len(os.Args) > 2 {
			root = os.Args[2]
		}
		cleanup(root)
		return
	}

	root := readInstallRoot()
	if root == "" {
		root = "D:\\Software\\知屿"
	}

	// 先结束主程序
	silent("taskkill", "/f", "/im", "知屿.exe")
	time.Sleep(500 * time.Millisecond)

	r := msgBox("卸载知屿",
		"确定要卸载知屿吗？\n\n将删除程序文件、桌面快捷方式与开机自启项。\n你的云端笔记数据不受影响（保存在服务器）。",
		MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2)
	if r != IDYES {
		return
	}

	// 结束主程序（再次确保）
	silent("taskkill", "/f", "/im", "知屿.exe")

	// 删除桌面快捷方式（用户桌面 + 公共桌面）
	for _, dir := range []string{os.Getenv("USERPROFILE") + `\Desktop`, `C:\Users\Public\Desktop`} {
		os.Remove(filepath.Join(dir, "知屿.lnk"))
	}

	// 删除注册表卸载项 + 开机自启
	silent("reg", "delete", `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿`, "/f")
	silent("reg", "delete", `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿`, "/f")
	silent("reg", "delete", `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, "/v", "知屿", "/f")

	// 复制自己到临时目录（--cleanup 副本），由它删除整个安装目录（此时原进程退出，文件无占用）
	tmpSelf := filepath.Join(os.TempDir(), "zhiyu-uninst-cleanup.exe")
	if err := copyFile(os.Args[0], tmpSelf); err == nil {
		cmd := exec.Command(tmpSelf, "--cleanup", root)
		cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
		cmd.Start()
	} else {
		// 复制失败兜底：直接尝试删除（尽力而为）
		os.RemoveAll(root)
	}

	msgBox("卸载完成", "知屿 已卸载完成。", MB_OK|MB_ICONINFORMATION)
	fmt.Println("uninstalled")
}
