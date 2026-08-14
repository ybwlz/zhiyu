// 知屿桌面版 Tauri 主程序：复用 Electron 版前端，用本地 HTTP 服务 + API 代理
use axum::{
    body::Body,
    http::{Request, Response, StatusCode},
    routing::any,
    Router,
};
use std::sync::Arc;
use tauri::{
    menu::{Menu, MenuItem},
    tray::{TrayIconBuilder, TrayIconEvent},
    Manager,
};

const PORT: u16 = 51780;
const DEFAULT_BACKEND: &str = "http://182.254.209.123";
const UPDATE_URL: &str = "http://182.254.209.123/downloads/version.json";

// 前端靠 navigator.userAgent.includes('Electron') 判断桌面模式（决定是否显示 -□× 窗口按钮、
// 隐藏下载按钮、把导航栏当标题栏）。Tauri 用 WebView2，UA 里没有 Electron，故这里补上，
// 让前端零改动就按桌面版渲染（与 Electron 版行为完全一致）。
const USER_AGENT: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
(KHTML, like Gecko) zhiyu/1.2.0 Chrome/131.0.0.0 Electron/33.0.0 Safari/537.36";

// ── 后端地址 ──
fn resolve_backend() -> String {
    if let Ok(b) = std::env::var("ZHIYU_BACKEND") {
        if !b.is_empty() {
            return b;
        }
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            let cfg = dir.join("config.json");
            if let Ok(txt) = std::fs::read_to_string(cfg) {
                if let Ok(v) = serde_json::from_str::<serde_json::Value>(&txt) {
                    if let Some(b) = v.get("backend").and_then(|x| x.as_str()) {
                        if !b.is_empty() {
                            return b.to_string();
                        }
                    }
                }
            }
        }
    }
    DEFAULT_BACKEND.to_string()
}

// ── 代理：完整转发请求头 + 响应头（Electron 版就是 ...req.headers 全转发）。
//    之前漏了 header，导致头像上传（multipart 需 Content-Type boundary）、
//    登录态（Authorization/Cookie）、附件下载（Content-Disposition）等出问题。 ──
async fn proxy(req: Request<Body>, backend: &str, path: &str, query: Option<&str>) -> Response<Body> {
    let client = reqwest::Client::new();
    let mut target = format!("{}{}", backend, path);
    if let Some(q) = query {
        target.push('?');
        target.push_str(q);
    }
    let method = req.method().clone();

    // 转发请求头（排除 hop-by-hop 头，host/connection 等由 reqwest 自行处理）
    let mut req_builder = client.request(method, &target);
    for (name, value) in req.headers() {
        let n = name.as_str().to_ascii_lowercase();
        if matches!(
            n.as_str(),
            "host"
                | "connection"
                | "content-length"
                | "transfer-encoding"
                | "keep-alive"
                | "upgrade"
                | "proxy-connection"
                | "te"
                | "trailer"
        ) {
            continue;
        }
        req_builder = req_builder.header(name.clone(), value.clone());
    }

    let body = req.into_body();
    let bytes = match axum::body::to_bytes(body, 200 * 1024 * 1024).await {
        Ok(b) => b,
        Err(_) => return Response::builder().status(500).body(Body::from("body too large")).unwrap(),
    };
    let resp = req_builder.body(bytes.to_vec()).send().await;
    match resp {
        Ok(r) => {
            let status = r.status();
            let resp_headers = r.headers().clone();
            match r.bytes().await {
                Ok(b) => {
                    let mut builder = Response::builder().status(status);
                    for (name, value) in resp_headers {
                        if let (Some(name), Ok(v)) = (name, value.to_str()) {
                            builder = builder.header(name, v);
                        }
                    }
                    builder
                        .body(Body::from(b.to_vec()))
                        .unwrap_or_else(|_| Response::builder().status(500).body(Body::empty()).unwrap())
                }
                Err(_) => Response::builder().status(status).body(Body::empty()).unwrap(),
            }
        }
        Err(_) => Response::builder()
            .status(StatusCode::BAD_GATEWAY)
            .body(Body::from("Backend unavailable"))
            .unwrap(),
    }
}

async fn serve_frontend(req: Request<Body>, dist: Arc<String>) -> Response<Body> {
    let p = req.uri().path().to_string();
    if p.starts_with("/zhiyu") {
        let idx = format!("{}/index.html", dist);
        match tokio::fs::read(idx).await {
            Ok(b) => Response::builder()
                .header("content-type", "text/html; charset=utf-8")
                .body(Body::from(b))
                .unwrap(),
            Err(_) => Response::builder().status(404).body(Body::from("Not Found")).unwrap(),
        }
    } else {
        let rel = p.trim_start_matches('/');
        let file = std::path::Path::new(dist.as_str()).join(if rel.is_empty() { "index.html" } else { rel });
        match tokio::fs::read(&file).await {
            Ok(b) => {
                let ct = mime_type(&file.to_string_lossy());
                Response::builder().header("content-type", ct).body(Body::from(b)).unwrap()
            }
            Err(_) => {
                if p == "/" || p.is_empty() {
                    let idx = format!("{}/index.html", dist);
                    if let Ok(b) = tokio::fs::read(idx).await {
                        return Response::builder()
                            .header("content-type", "text/html; charset=utf-8")
                            .body(Body::from(b))
                            .unwrap();
                    }
                }
                Response::builder().status(404).body(Body::from("Not Found")).unwrap()
            }
        }
    }
}

fn mime_type(file: &str) -> &'static str {
    let ext = std::path::Path::new(file).extension().and_then(|e| e.to_str()).unwrap_or("");
    match ext {
        "html" => "text/html; charset=utf-8",
        "js" => "text/javascript; charset=utf-8",
        "css" => "text/css; charset=utf-8",
        "json" => "application/json",
        "svg" => "image/svg+xml",
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "gif" => "image/gif",
        "webp" => "image/webp",
        "ico" => "image/x-icon",
        "woff" => "font/woff",
        "woff2" => "font/woff2",
        "ttf" => "font/ttf",
        _ => "application/octet-stream",
    }
}

async fn start_server(dist: String, backend: String) {
    let dist_arc = Arc::new(dist.clone());
    let backend_arc = Arc::new(backend.clone());
    let app = Router::new()
        .route("/api/*path", any({
            let b = backend_arc.clone();
            move |req: Request<Body>| {
                let b = b.clone();
                async move {
                    let path = req.uri().path().to_string();
                    let query = req.uri().query().map(|q| q.to_string());
                    proxy(req, &b, &path, query.as_deref()).await
                }
            }
        }))
        .route("/uploads/*path", any({
            let b = backend_arc.clone();
            move |req: Request<Body>| {
                let b = b.clone();
                async move {
                    let path = req.uri().path().to_string();
                    let query = req.uri().query().map(|q| q.to_string());
                    proxy(req, &b, &path, query.as_deref()).await
                }
            }
        }))
        .fallback({
            let d = dist_arc.clone();
            move |req: Request<Body>| {
                let d = d.clone();
                async move { serve_frontend(req, d).await }
            }
        });
    let listener = tokio::net::TcpListener::bind(("127.0.0.1", PORT)).await.unwrap();
    let _ = axum::serve(listener, app).await;
}

// ── Tauri commands（对应 Electron preload 的 window.desktop） ──
#[tauri::command]
fn app_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

#[tauri::command]
fn set_title_bar_color(_window: tauri::Window, _color: String) {
    // Tauri 的 WebView 背景由前端 HTML 决定，主题切换时前端已改背景，无需额外设置
}

#[tauri::command]
fn set_auto_launch(app: tauri::AppHandle, enabled: bool) -> Result<(), String> {
    use tauri_plugin_autostart::ManagerExt;
    let m = app.autolaunch();
    if enabled {
        m.enable().map_err(|e| e.to_string())
    } else {
        m.disable().map_err(|e| e.to_string())
    }
}

#[tauri::command]
fn get_auto_launch(app: tauri::AppHandle) -> bool {
    use tauri_plugin_autostart::ManagerExt;
    app.autolaunch().is_enabled().unwrap_or(false)
}

#[tauri::command]
fn quit_app(app: tauri::AppHandle) {
    app.exit(0);
}

#[tauri::command]
fn is_uninstall_mode() -> bool {
    std::env::args().any(|a| a == "--uninstall")
}

#[tauri::command]
fn uninstall_app(app: tauri::AppHandle) {
    // 删注册表 + 快捷方式 + 延迟删整个目录
    let _ = std::process::Command::new("reg")
        .args(["delete", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿", "/f"])
        .output();
    let _ = std::process::Command::new("reg")
        .args(["delete", r"HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿", "/f"])
        .output();
    let _ = std::process::Command::new("reg")
        .args(["delete", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run", "/v", "知屿", "/f"])
        .output();
    if let Ok(exe) = std::env::current_exe() {
        if let Some(root) = exe.parent() {
            let root_s = root.to_string_lossy().to_string();
            let bat = format!(
                "@echo off\r\nchcp 65001 >nul\r\ntimeout /t 3 /nobreak >nul\r\ntaskkill /f /im zhiyu.exe >nul 2>&1\r\ntimeout /t 2 /nobreak >nul\r\nrmdir /s /q \"{}\" >nul 2>&1\r\ndel \"%~f0\" >nul 2>&1\r\n",
                root_s
            );
            let tmp = std::env::temp_dir();
            let bp = tmp.join(format!("zhiyu-uninst-{}.bat", std::process::id()));
            let _ = std::fs::write(&bp, bat.as_bytes());
            let _ = std::process::Command::new("cmd").args(["/c", &bp.to_string_lossy()]).spawn();
        }
    }
    app.exit(0);
}

#[tauri::command]
async fn check_update() -> Option<serde_json::Value> {
    let client = reqwest::Client::new();
    let resp = client.get(UPDATE_URL).send().await.ok()?;
    let data: serde_json::Value = resp.json().await.ok()?;
    let new_ver = data.get("version")?.as_str()?;
    let cur = env!("CARGO_PKG_VERSION");
    if compare_version(new_ver, cur) > 0 {
        Some(data)
    } else {
        None
    }
}

fn compare_version(a: &str, b: &str) -> i32 {
    let pa: Vec<u32> = a.split('.').map(|x| x.parse().unwrap_or(0)).collect();
    let pb: Vec<u32> = b.split('.').map(|x| x.parse().unwrap_or(0)).collect();
    for i in 0..3 {
        let x = pa.get(i).copied().unwrap_or(0);
        let y = pb.get(i).copied().unwrap_or(0);
        if x != y {
            return x as i32 - y as i32;
        }
    }
    0
}

// ── window.desktop 注入脚本 ──
fn inject_desktop_script() -> &'static str {
    r#"
Object.defineProperty(window, 'desktop', {
  value: {
    setTitleBarColor: (color) => window.__TAURI__.core.invoke('set_title_bar_color', { color }),
    windowControls: {
      minimize: () => window.__TAURI__.window.getCurrentWindow().minimize(),
      maximize: () => window.__TAURI__.window.getCurrentWindow().toggleMaximize(),
      close: () => window.__TAURI__.window.getCurrentWindow().close(),
    },
    appVersion: () => window.__TAURI__.core.invoke('app_version'),
    setAutoLaunch: (enabled) => window.__TAURI__.core.invoke('set_auto_launch', { enabled }),
    getAutoLaunch: () => window.__TAURI__.core.invoke('get_auto_launch'),
    hideToTray: () => window.__TAURI__.window.getCurrentWindow().hide(),
    quitApp: () => window.__TAURI__.core.invoke('quit_app'),
    isUninstallMode: () => window.__TAURI__.core.invoke('is_uninstall_mode'),
    uninstallApp: () => window.__TAURI__.core.invoke('uninstall_app'),
    checkUpdate: () => window.__TAURI__.core.invoke('check_update'),
    onUpdateAvailable: () => {},
    downloadUpdate: () => window.__TAURI__.core.invoke('download_update'),
    pauseUpdate: () => {},
    cancelUpdate: () => {},
    onUpdateProgress: () => {},
    onUpdateCancelled: () => {},
  }
});

// 无边框窗口拖拽：桌面模式下导航栏/编辑顶栏作标题栏可拖动。
// Electron 用 -webkit-app-region:drag，WebView2 不认，改用 startDragging。
// 命中按钮/输入框/链接/主题菜单等交互元素时不触发拖拽，保证可正常点击。
document.addEventListener('mousedown', (e) => {
  const t = e.target;
  if (!(t instanceof Element)) return;
  const bar = t.closest('.kb-navbar, .edit-topbar');
  if (!bar) return;
  if (t.closest('button, input, select, textarea, a, label, [role="button"], .nav-right, .kb-theme-menu, .kb-theme-wrap, .vis-seg')) return;
  try { window.__TAURI__.window.getCurrentWindow().startDragging(); } catch (_) {}
});
"#
}

pub fn run() {
    let backend = resolve_backend();
    let dist = {
        let exe = std::env::current_exe().unwrap();
        let dir = exe.parent().unwrap().to_path_buf();
        let candidates = [
            dir.join("dist-electron"),
            dir.join("..").join("dist-electron"),
            dir.join("..").join("..").join("dist-electron"),
            dir.join("..").join("..").join("..").join("dist-electron"),
            dir.join("..").join("..").join("..").join("..").join("dist-electron"),
        ];
        candidates
            .iter()
            .find(|c| c.join("index.html").exists())
            .map(|c| c.to_string_lossy().to_string())
            .unwrap_or_else(|| dir.join("dist-electron").to_string_lossy().to_string())
    };

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.unminimize();
                let _ = w.show();
                let _ = w.set_focus();
            }
        }))
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            None,
        ))
        .invoke_handler(tauri::generate_handler![
            app_version,
            set_title_bar_color,
            set_auto_launch,
            get_auto_launch,
            quit_app,
            is_uninstall_mode,
            uninstall_app,
            check_update
        ])
        .setup(move |app| {
            let dist_clone = dist.clone();
            let backend_clone = backend.clone();
            tauri::async_runtime::spawn(async move {
                start_server(dist_clone, backend_clone).await;
            });

            // 托盘
            let show = MenuItem::with_id(app, "show", "显示知屿", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;
            // 应用图标：用 256×256 PNG（从 icon.ico 提取），保证窗口/托盘图标清晰。
            // default_window_icon() 从多帧 ICO 里取的可能只有小尺寸帧，导致任务栏图标发糊。
            let app_icon = tauri::image::Image::from_bytes(include_bytes!("../icons/icon-256.png")).ok();
            let mut tray_builder = TrayIconBuilder::new().menu(&menu);
            if let Some(ic) = &app_icon {
                tray_builder = tray_builder.icon(ic.clone());
            }
            let _tray = tray_builder
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.unminimize();
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "quit" => app.exit(0),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click { .. } = event {
                        let app = tray.app_handle();
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.unminimize();
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                })
                .build(app)?;

            let url = format!("http://127.0.0.1:{}", PORT).parse().unwrap();
            let win_builder = tauri::WebviewWindowBuilder::new(app, "main", tauri::WebviewUrl::External(url))
                .title("知屿")
                .inner_size(1280.0, 860.0)
                .min_inner_size(940.0, 640.0)
                .decorations(false)
                .user_agent(USER_AGENT)
                // WebView2(Win11) 默认用 Fluent 覆盖式滚动条（自动隐藏、忽略 ::-webkit-scrollbar），
                // 关掉它让前端细滚动条像 Electron 一样常驻显示
                .additional_browser_args("--disable-features=OverlayScrollbar,FluentOverlayScrollbar")
                .initialization_script(inject_desktop_script());
            let _win = win_builder.build()?;
            if let Some(ic) = &app_icon {
                let _ = _win.set_icon(ic.clone());
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
