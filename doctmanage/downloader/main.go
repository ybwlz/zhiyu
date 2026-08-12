// 知屿下载器：从服务器拉取完整安装包 → 解压 → 可选启动
// 用法：编译为 Windows exe 后放到下载页；双击运行即可。
//go:build windows

package main

import (
	"archive/zip"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"time"
	"unicode/utf16"
	"unsafe"
)

// 完整包地址（服务器 /downloads/）
const PACK_URL = "http://182.254.209.123/downloads/zhiyu-win32-x64.zip"

var (
	user32           = syscall.NewLazyDLL("user32.dll")
	procMessageBoxW  = user32.NewProc("MessageBoxW")
	kernel32        = syscall.NewLazyDLL("kernel32.dll")
	procSetTitle     = kernel32.NewProc("SetConsoleTitleW")
)

func utf16Ptr(s string) *uint16 {
	u := utf16.Encode([]rune(s + "\x00"))
	return &u[0]
}

func setTitle(title string) {
	procSetTitle.Call(uintptr(unsafePtr(utf16Ptr(title))))
}

// unsafePtr 转换
func unsafePtr(p *uint16) uintptr {
	return uintptr(unsafe.Pointer(p))
}

func msgbox(text, title string, flags uint) int {
	r, _, _ := procMessageBoxW.Call(0, uintptr(unsafePtr(utf16Ptr(text))), uintptr(unsafePtr(utf16Ptr(title))), uintptr(flags))
	return int(r)
}

func main() {
	setTitle("知屿下载器")
	fmt.Println("======================================")
	fmt.Println("  知屿 · 桌面版下载器")
	fmt.Println("  正在准备下载安装包，请稍候...")
	fmt.Println("======================================")

	tmp := filepath.Join(os.TempDir(), "zhiyu-setup.zip")
	if err := download(PACK_URL, tmp); err != nil {
		fmt.Println("\n下载失败：", err)
		msgbox("知屿安装包下载失败：\n"+err.Error()+"\n请检查网络后重试。", "知屿下载器", 0x10 /*MB_ICONERROR*/)
		os.Exit(1)
	}

	fmt.Println("\n正在解压安装...")
	exeDir, err := os.Getwd()
	if err != nil {
		exeDir = "."
	}
	dest := filepath.Join(exeDir, "zhiyu-win32-x64")
	if err := unzip(tmp, dest); err != nil {
		fmt.Println("\n解压失败：", err)
		msgbox("安装包解压失败：\n"+err.Error(), "知屿下载器", 0x10)
		os.Exit(1)
	}
	os.Remove(tmp)

	app := filepath.Join(dest, "知屿.exe")
	fmt.Println("\n======================================")
	fmt.Println("  ✅ 知屿桌面版安装完成！")
	fmt.Println("  位置：", dest)
	fmt.Println("======================================")

	// 询问是否启动
	choice := msgbox("知屿桌面版已安装完成，是否立即启动？\n\n安装位置："+dest, "知屿下载器", 0x4|0x40 /*MB_YESNO|MB_ICONINFORMATION*/)
	if choice == 6 { // IDYES
		if err := startApp(app); err != nil {
			msgbox("启动失败，请手动打开：\n"+app, "知屿下载器", 0x10)
		}
	}
}

func download(url, dest string) error {
	client := &http.Client{Timeout: 30 * time.Minute}
	resp, err := client.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return fmt.Errorf("服务器返回 %d", resp.StatusCode)
	}

	total := resp.ContentLength
	f, err := os.Create(dest)
	if err != nil {
		return err
	}
	defer f.Close()

	buf := make([]byte, 256*1024)
	var done int64
	start := time.Now()
	for {
		n, rerr := resp.Body.Read(buf)
		if n > 0 {
			f.Write(buf[:n])
			done += int64(n)
			// 进度条
			pct := float64(0)
			if total > 0 {
				pct = float64(done) / float64(total) * 100
			}
			mb := float64(done) / 1024 / 1024
			speed := float64(done) / 1024 / 1024 / time.Since(start).Seconds()
			fmt.Printf("\r  下载中 %5.1f%%  %.0f MB  (%.1f MB/s)  ", pct, mb, speed)
		}
		if rerr == io.EOF {
			break
		}
		if rerr != nil {
			return rerr
		}
	}
	fmt.Println()
	return nil
}

func unzip(src, dest string) error {
	r, err := zip.OpenReader(src)
	if err != nil {
		return err
	}
	defer r.Close()
	os.MkdirAll(dest, 0755)
	for _, f := range r.File {
		// 防路径穿越
		name := strings.ReplaceAll(f.Name, "\\", "/")
		if strings.Contains(name, "..") {
			continue
		}
		target := filepath.Join(dest, name)
		if f.FileInfo().IsDir() {
			os.MkdirAll(target, 0755)
			continue
		}
		os.MkdirAll(filepath.Dir(target), 0755)
		rc, err := f.Open()
		if err != nil {
			return err
		}
		out, err := os.Create(target)
		if err != nil {
			rc.Close()
			return err
		}
		_, err = io.Copy(out, rc)
		rc.Close()
		out.Close()
		if err != nil {
			return err
		}
	}
	return nil
}

func startApp(exe string) error {
	pathp, err := syscall.UTF16PtrFromString(exe)
	if err != nil {
		return err
	}
	var si syscall.StartupInfo
	var pi syscall.ProcessInformation
	return syscall.CreateProcess(
		pathp, nil, nil, nil, false,
		0x00000010 /*CREATE_NEW_CONSOLE*/, nil, nil, &si, &pi)
}
