// 知屿卸载器：删除安装目录 + 公共桌面快捷方式 + 注册表卸载项
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

var (
	user32         = syscall.NewLazyDLL("user32.dll")
	procMessageBox = user32.NewProc("MessageBoxW")
)

func msgBox(title, text string) {
	hwnd := uintptr(0)
	procMessageBox.Call(hwnd, uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr(text))), uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr(title))), 0x40)
}

// 从注册表读卸载项的字符串值
func regQueryString(subKey, name string) string {
	cmd := exec.Command("reg", "query", subKey, "/v", name)
	out, err := cmd.Output()
	if err != nil {
		return ""
	}
	// 输出形如:    InstallLocation    REG_SZ    D:\Software\知屿
	lines := strings.Split(string(out), "\r\n")
	for _, l := range lines {
		l = strings.TrimSpace(l)
		if strings.Contains(l, name) {
			parts := strings.Fields(l)
			if len(parts) >= 3 {
				// 路径可能含空格：取第一个 REG_SZ 之后的部分
				idx := strings.Index(l, "REG_SZ")
				if idx >= 0 {
					return strings.TrimSpace(l[idx+len("REG_SZ"):])
				}
			}
		}
	}
	return ""
}

func main() {
	fmt.Println("知屿卸载程序")
	fmt.Println("正在结束知屿进程…")

	// 结束知屿进程
	exec.Command("taskkill", "/f", "/im", "知屿.exe").Run()
	exec.Command("taskkill", "/f", "/im", "知屿安装器.exe").Run()
	time.Sleep(500 * time.Millisecond)

	// 卸载目标目录（优先读注册表 InstallLocation，找不到则默认）
	subKey := `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿`
	installDir := regQueryString(subKey, "InstallLocation")
	if installDir == "" {
		installDir = "D:\\Software\\知屿"
	}

	fmt.Println("删除安装目录:", installDir)
	os.RemoveAll(installDir)

	// 公共桌面 + 用户桌面快捷方式
	for _, dir := range []string{`C:\Users\Public\Desktop`, os.Getenv("USERPROFILE") + `\Desktop`} {
		for _, name := range []string{"知屿.lnk", "知屿安装器.lnk"} {
			p := filepath.Join(dir, name)
			if _, err := os.Stat(p); err == nil {
				fmt.Println("删除快捷方式:", p)
				os.Remove(p)
			}
		}
	}

	// 注册表卸载项（HKCU + HKLM 都尝试）
	exec.Command("reg", "delete", subKey, "/f").Run()
	exec.Command("reg", "delete", `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿`, "/f").Run()

	fmt.Println("完成")
	msgBox("知屿", "知屿 已卸载完成。")
}
