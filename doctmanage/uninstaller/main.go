// 知屿卸载器（Go 自绘深色界面，2MB 轻量，风格与主程序一致）
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
	user32   = syscall.NewLazyDLL("user32.dll")
	gdi32    = syscall.NewLazyDLL("gdi32.dll")
	kernel32 = syscall.NewLazyDLL("kernel32.dll")

	procRegisterClass    = user32.NewProc("RegisterClassW")
	procCreateWindowEx   = user32.NewProc("CreateWindowExW")
	procDefWindowProc    = user32.NewProc("DefWindowProcW")
	procDestroyWindow    = user32.NewProc("DestroyWindow")
	procPostQuitMessage  = user32.NewProc("PostQuitMessage")
	procGetMessage       = user32.NewProc("GetMessageW")
	procTranslateMessage = user32.NewProc("TranslateMessage")
	procDispatchMessage  = user32.NewProc("DispatchMessageW")
	procShowWindow       = user32.NewProc("ShowWindow")
	procUpdateWindow     = user32.NewProc("UpdateWindow")
	procGetDC            = user32.NewProc("GetDC")
	procReleaseDC        = user32.NewProc("ReleaseDC")
	procInvalidateRect   = user32.NewProc("InvalidateRect")
	procGetSystemMetrics = user32.NewProc("GetSystemMetrics")
	procLoadCursor       = user32.NewProc("LoadCursorW")
	procSetCursor        = user32.NewProc("SetCursor")
	procGetModuleHandle  = kernel32.NewProc("GetModuleHandleW")
	procFillRect         = user32.NewProc("FillRect")
	procDrawText         = user32.NewProc("DrawTextW")
	procCreateSolidBrush = gdi32.NewProc("CreateSolidBrush")
	procCreateFont       = gdi32.NewProc("CreateFontW")
	procSelectObject     = gdi32.NewProc("SelectObject")
	procDeleteObject     = gdi32.NewProc("DeleteObject")
	procSetTextColor     = gdi32.NewProc("SetTextColor")
	procSetBkMode        = gdi32.NewProc("SetBkMode")
	procSetBkColor       = gdi32.NewProc("SetBkColor")
	procGetClientRect    = user32.NewProc("GetClientRect")
	procMoveWindow       = user32.NewProc("MoveWindow")
	procSetWindowPos     = user32.NewProc("SetWindowPos")
	procGetWindowLong    = user32.NewProc("GetWindowLongW")
	procSetWindowLong    = user32.NewProc("SetWindowLongW")
)

const (
	WM_PAINT      = 0x000F
	WM_LBUTTONDOWN = 0x0201
	WM_LBUTTONUP  = 0x0202
	WM_MOUSEMOVE  = 0x0200
	WM_ERASEBKGND = 0x0014
	WM_CLOSE      = 0x0010
	WM_DESTROY    = 0x0002
	WM_SETCURSOR  = 0x0020
	WS_POPUP      = 0x80000000
	WS_VISIBLE    = 0x10000000
	TRANSPARENT   = 1
	SM_CXSCREEN   = 0
	SM_CYSCREEN   = 1
	IDC_ARROW     = 32512
)

// 主题色
const (
	BG       = 0x0d1220 // 深空背景
	CARD     = 0x121a2e
	TEXT1    = 0xe8ecf8 // 主文字
	TEXT2    = 0x8b96b0 // 次级文字
	BRAND    = 0x4f8ef7 // 品牌蓝
	DANGER   = 0xe11d48 // 危险红
	BORDER   = 0x2a3550
	BTN_BG   = 0x1c2740
)

var (
	hwnd     uintptr
	hFont    uintptr
	hFontBig uintptr
	hFontMid uintptr
	state    = 0 // 0=确认, 1=卸载中, 2=完成
	progress = 0
	status   = ""
	hoverBtn = 0 // 0=无, 1=取消, 2=确认卸载, 3=确定
	mouseDown = 0
	installRoot = ""
)

func strptr(s string) uintptr { return uintptr(unsafe.Pointer(syscall.StringToUTF16Ptr(s))) }

func makeFont(size int, bold bool) uintptr {
	fw := uintptr(0)
	if bold { fw = 700 }
	r, _, _ := procCreateFont.Call(uintptr(-size), 0, 0, 0, fw, 0, 0, 0, 0x86, 0, 0, 0x4 /*CLEARTYPE_QUALITY*/, 0, strptr("Microsoft YaHei UI"))
	return r
}

func wndProc(h, msg, w, l uintptr) uintptr {
	switch msg {
	case WM_ERASEBKGND:
		return 1
	case WM_PAINT:
		draw()
		return 0
	case WM_MOUSEMOVE:
		x := int(int16(l & 0xffff)); y := int(int16((l >> 16) & 0xffff))
		h := btnAt(x, y)
		if h != hoverBtn { hoverBtn = h; repaint() }
		return 0
	case WM_LBUTTONDOWN:
		x := int(int16(l & 0xffff)); y := int(int16((l >> 16) & 0xffff))
		mouseDown = btnAt(x, y)
		return 0
	case WM_LBUTTONUP:
		x := int(int16(l & 0xffff)); y := int(int16((l >> 16) & 0xffff))
		b := btnAt(x, y)
		if b != 0 && b == mouseDown { onButton(b) }
		mouseDown = 0
		return 0
	case WM_SETCURSOR:
		cur, _, _ := procLoadCursor.Call(0, IDC_ARROW)
		procSetCursor.Call(cur)
		return 1
	case WM_CLOSE:
		if state == 0 || state == 2 { procDestroyWindow.Call(h) }
		return 0
	case WM_DESTROY:
		procPostQuitMessage.Call(0)
		return 0
	}
	r, _, _ := procDefWindowProc.Call(h, msg, w, l)
	return r
}

// 按钮区域（基于 400x320）
func btnRect(btn int) (int, int, int, int) {
	switch btn {
	case 1: // 取消
		return 90, 240, 170, 278
	case 2: // 确认卸载
		return 210, 240, 310, 278
	case 3: // 确定
		return 150, 250, 250, 288
	}
	return 0, 0, 0, 0
}
func btnAt(x, y int) int {
	for b := 1; b <= 3; b++ {
		x0, y0, x1, y1 := btnRect(b)
		if state == 0 && b == 3 { continue }
		if state == 2 && b <= 2 { continue }
		if x >= x0 && x <= x1 && y >= y0 && y <= y1 { return b }
	}
	return 0
}

func draw() {
	dc, _, _ := procGetDC.Call(hwnd)
	if dc == 0 { return }
	// 背景
	bgBrush, _, _ := procCreateSolidBrush.Call(BG)
	var rc struct{ Left, Top, Right, Bottom int32 }
	procGetClientRect.Call(hwnd, uintptr(unsafe.Pointer(&rc)))
	rc2 := &rc
	procFillRect.Call(dc, uintptr(unsafe.Pointer(rc2)), bgBrush)
	procDeleteObject.Call(bgBrush)

	procSetBkMode.Call(dc, TRANSPARENT)
	procSelectObject.Call(dc, hFontBig)
	procSetTextColor.Call(dc, TEXT1)
	// 标题"知屿"
	titleRect := rc; titleRect.Top = 26; titleRect.Bottom = 74
	procDrawText.Call(dc, strptr("知屿"), 0xFFFFFFFFFFFFFFFF, uintptr(unsafe.Pointer(&titleRect)), 0x0001 /*DT_CENTER*/)
	// "卸载知屿？"
	procSelectObject.Call(dc, hFontMid)
	procSetTextColor.Call(dc, TEXT1)
	qRect := rc; qRect.Top = 84; qRect.Bottom = 122
	procDrawText.Call(dc, strptr("卸载知屿？"), 0xFFFFFFFFFFFFFFFF, uintptr(unsafe.Pointer(&qRect)), 0x0001)
	// 说明
	procSelectObject.Call(dc, hFont)
	procSetTextColor.Call(dc, TEXT2)
	d1 := rc; d1.Top = 130; d1.Bottom = 158
	procDrawText.Call(dc, strptr("将删除程序文件、桌面快捷方式与开机自启项。"), 0xFFFFFFFFFFFFFFFF, uintptr(unsafe.Pointer(&d1)), 0x0001)
	d2 := rc; d2.Top = 158; d2.Bottom = 186
	procDrawText.Call(dc, strptr("云端笔记数据不受影响（保存在服务器）。"), 0xFFFFFFFFFFFFFFFF, uintptr(unsafe.Pointer(&d2)), 0x0001)

	// 卸载中：进度条 + 状态
	if state == 1 {
		// 进度条背景
		pbBrush, _, _ := procCreateSolidBrush.Call(BORDER)
		pr := rc; pr.Top = 196; pr.Bottom = 212; pr.Left = 60; pr.Right = 340
		procFillRect.Call(dc, uintptr(unsafe.Pointer(&pr)), pbBrush)
		procDeleteObject.Call(pbBrush)
		// 进度
		if progress > 0 {
			fb, _, _ := procCreateSolidBrush.Call(BRAND)
			fr := pr; fr.Right = fr.Left + int32((fr.Right-fr.Left)*int32(progress)/100)
			if fr.Right > fr.Left { procFillRect.Call(dc, uintptr(unsafe.Pointer(&fr)), fb) }
			procDeleteObject.Call(fb)
		}
		procSelectObject.Call(dc, hFont)
		procSetTextColor.Call(dc, TEXT2)
		st := rc; st.Top = 216; st.Bottom = 244
		procDrawText.Call(dc, strptr(fmt.Sprintf("%s（%d%%）", status, progress)), 0xFFFFFFFFFFFFFFFF, uintptr(unsafe.Pointer(&st)), 0x0001)
	}

	// 按钮
	drawBtn := func(b int, text string, danger, hover bool) {
		x0, y0, x1, y1 := btnRect(b)
		var col uintptr
		if danger { col = DANGER } else { col = BTN_BG }
		if hover { col = col + 0x101010 }
		brush, _, _ := procCreateSolidBrush.Call(col)
		var br struct{ Left, Top, Right, Bottom int32 }
		br.Left, br.Top, br.Right, br.Bottom = int32(x0), int32(y0), int32(x1), int32(y1)
		procFillRect.Call(dc, uintptr(unsafe.Pointer(&br)), brush)
		procDeleteObject.Call(brush)
		// 边框
		bdBrush, _, _ := procCreateSolidBrush.Call(BORDER)
		var bdr struct{ Left, Top, Right, Bottom int32 }
		bdr.Left, bdr.Top, bdr.Right, bdr.Bottom = int32(x0), int32(y0), int32(x1), int32(y1)
		procFillRect.Call(dc, uintptr(unsafe.Pointer(&bdr)), bdBrush)
		procDeleteObject.Call(bdBrush)
		procSelectObject.Call(dc, hFont)
		if danger { procSetTextColor.Call(dc, 0xff6b81) } else { procSetTextColor.Call(dc, TEXT1) }
		var tr struct{ Left, Top, Right, Bottom int32 }
		tr.Left, tr.Top, tr.Right, tr.Bottom = int32(x0), int32(y0), int32(x1), int32(y1)
		procDrawText.Call(dc, strptr(text), 0xFFFFFFFFFFFFFFFF, uintptr(unsafe.Pointer(&tr)), 0x0001)
	}
	if state == 0 {
		drawBtn(1, "取消", false, hoverBtn == 1)
		drawBtn(2, "确认卸载", true, hoverBtn == 2)
	} else if state == 2 {
		drawBtn(3, "完成", false, hoverBtn == 3)
	}

	procReleaseDC.Call(hwnd, dc)
}

func repaint() { procInvalidateRect.Call(hwnd, 0, 1) }

func onButton(b int) {
	switch b {
	case 1: // 取消
		procDestroyWindow.Call(hwnd)
	case 2: // 确认卸载
		state = 1
		go doUninstall()
	case 3: // 完成
		finalizeDelete()
		procDestroyWindow.Call(hwnd)
	}
}

func runCmd(name string, args ...string) {
	exec.Command(name, args...).Run()
}

func doUninstall() {
	steps := []struct {
		pct int
		msg string
		fn  func()
	}{
		{15, "结束知屿进程…", func() { exec.Command("taskkill", "/f", "/im", "知屿.exe").Run() }},
		{35, "删除桌面快捷方式…", func() {
			for _, dir := range []string{os.Getenv("USERPROFILE") + `\Desktop`, `C:\Users\Public\Desktop`} {
				p := filepath.Join(dir, "知屿.lnk")
				if _, err := os.Stat(p); err == nil { os.Remove(p) }
			}
		}},
		{60, "删除注册表项…", func() {
			runCmd("reg", "delete", `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿`, "/f")
			runCmd("reg", "delete", `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿`, "/f")
			runCmd("reg", "delete", `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, "/v", "知屿", "/f")
		}},
		{85, "清理安装目录…", func() {
			// 主程序目录（本卸载器目录最后由 finalizeDelete 延迟删除）
			appDir := filepath.Join(installRoot, "知屿.exe")
			if _, err := os.Stat(appDir); err == nil {
				// 目录 = installRoot（单目录结构）
			}
		}},
	}
	for _, s := range steps {
		time.Sleep(150 * time.Millisecond)
		s.fn()
		progress = s.pct
		status = s.msg
		repaint()
	}
	progress = 100
	status = "卸载完成"
	repaint()
	time.Sleep(300 * time.Millisecond)
	state = 2
	repaint()
}

// 后台延迟删除整个安装目录（含卸载器自身）
func finalizeDelete() {
	ps := fmt.Sprintf("Start-Sleep -Seconds 2; Remove-Item -LiteralPath '%s' -Recurse -Force -ErrorAction SilentlyContinue", installRoot)
	cmd := exec.Command("powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	cmd.Start()
}

// 从注册表读安装目录
func readInstallRoot() string {
	keys := []string{
		`HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿`,
		`HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿`,
	}
	for _, k := range keys {
		out, err := exec.Command("reg", "query", k, "/v", "InstallLocation").Output()
		if err != nil { continue }
		lines := strings.Split(string(out), "\r\n")
		for _, l := range lines {
			if strings.Contains(l, "InstallLocation") {
				if idx := strings.Index(l, "REG_SZ"); idx >= 0 {
					v := strings.TrimSpace(l[idx+6:])
					if v != "" { return v }
				}
			}
		}
	}
	return ""
}

func main() {
	installRoot = readInstallRoot()
	if installRoot == "" {
		installRoot = "D:\\Software\\知屿"
	}

	// 注册窗口类
	className := "ZhiyuUninstaller"
	classNamePtr, _ := syscall.UTF16PtrFromString(className)
	wndprocPtr := syscall.NewCallback(wndProc)
	var wc struct {
		Style        uint32
		WndProc      uintptr
		CbClsExtra   int32
		CbWndExtra   int32
		HInstance    uintptr
		HIcon        uintptr
		HCursor      uintptr
		HbrBg        uintptr
		MenuName     *uint16
		ClassName    *uint16
	}
	wc.Style = 0
	wc.WndProc = wndprocPtr
	wc.HInstance, _, _ = procGetModuleHandle.Call(0)
	wc.HCursor, _, _ = procLoadCursor.Call(0, IDC_ARROW)
	wc.ClassName = classNamePtr
	procRegisterClass.Call(uintptr(unsafe.Pointer(&wc)))

	// 屏幕居中
	sw, _, _ := procGetSystemMetrics.Call(SM_CXSCREEN)
	sh, _, _ := procGetSystemMetrics.Call(SM_CYSCREEN)
	w, h := 400, 320
	x := (int(sw) - w) / 2
	y := (int(sh) - h) / 2

	hwnd, _, _ = procCreateWindowEx.Call(
		0, uintptr(unsafe.Pointer(classNamePtr)), strptr("知屿 卸载"),
		WS_POPUP|WS_VISIBLE,
		uintptr(x), uintptr(y), uintptr(w), uintptr(h),
		0, 0, wc.HInstance, 0,
	)

	hFont = makeFont(13, false)
	hFontBig = makeFont(34, true)
	hFontMid = makeFont(17, true)

	procShowWindow.Call(hwnd, 1)
	procUpdateWindow.Call(hwnd)

	var msg struct {
		Hwnd    uintptr
		Message uint32
		WParam  uintptr
		LParam  uintptr
		Time    uint32
		Pt      struct{ X, Y int32 }
	}
	for {
		r, _, _ := procGetMessage.Call(uintptr(unsafe.Pointer(&msg)), 0, 0, 0)
		if r == 0 { break }
		procTranslateMessage.Call(uintptr(unsafe.Pointer(&msg)))
		procDispatchMessage.Call(uintptr(unsafe.Pointer(&msg)))
	}
}
