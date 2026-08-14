// 知屿安装器 C++ 移植版 — D2D DeviceContext + DirectComposition（真透明）
#define _WIN32_WINNT 0x0A00
#include <windows.h>
#include <windowsx.h>
#include <dwmapi.h>
#include <d2d1.h>
#include <d2d1_1.h>
#include <dwrite.h>
#include <d3d11.h>
#include <dxgi1_2.h>
#include <dcomp.h>
#include <shlobj.h>
#include <shobjidl.h>
#include <objbase.h>
#include <cmath>
#include <string>
#include <vector>

#pragma comment(lib, "d2d1.lib")
#pragma comment(lib, "dwrite.lib")
#pragma comment(lib, "dwmapi.lib")
#pragma comment(lib, "d3d11.lib")
#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "dcomp.lib")
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "shell32.lib")

#define IDR_GREEN 101
static const int W = 860, H = 600;
static float g_scale = 1.0f;   // DPI 缩放（物理像素/逻辑像素）

static ID2D1Factory* g_factory = nullptr;
static ID2D1DeviceContext* g_rt = nullptr;
static IDWriteFactory* g_dw = nullptr;
static ID2D1SolidColorBrush* g_shadow = nullptr;
static ID3D11Device* g_d3d = nullptr;
static IDXGISwapChain1* g_swap = nullptr;
static IDCompositionDevice* g_dcomp = nullptr;
static IDCompositionTarget* g_dcompTarget = nullptr;
static IDCompositionVisual* g_dcompVisual = nullptr;
static ID2D1Bitmap1* g_target = nullptr;

static IDWriteTextFormat *f_title=nullptr,*f_check=nullptr,*f_h1_26=nullptr,*f_h1=nullptr,*f_h1L=nullptr,*f_h2=nullptr,
    *f_body=nullptr,*f_btn=nullptr,*f_btnGhost=nullptr,*f_btnDanger=nullptr,*f_tb=nullptr,*f_name=nullptr,
    *f_label=nullptr,*f_labelC=nullptr,*f_sub=nullptr,*f_subC=nullptr,*f_cardName=nullptr,*f_small=nullptr,
    *f_themeDesc=nullptr,*f_themeName=nullptr,*f_badge=nullptr,*f_termsTitle=nullptr,*f_emoji=nullptr;

static ID2D1SolidColorBrush *g_white=nullptr,*g_text=nullptr,*g_dim=nullptr,*g_red=nullptr,*g_blue=nullptr,
    *g_blueGlow=nullptr,*g_closeRed=nullptr,*g_card=nullptr,*g_cardBorder=nullptr,*g_ghost=nullptr,*g_border=nullptr,
    *g_themeRow=nullptr,*g_titleHover=nullptr,*g_themeHover=nullptr,*g_chkBorder=nullptr,*g_progressBg=nullptr,
    *g_redBg=nullptr,*g_redBgH=nullptr,*g_redBorder=nullptr,*g_overlay=nullptr,*g_modalBg=nullptr,*g_blueTint=nullptr,*g_blueTintH=nullptr;
static ID2D1RoundedRectangleGeometry* g_clipGeo=nullptr;
static ID2D1StrokeStyle* g_stroke=nullptr;
static ID2D1RadialGradientBrush* g_bg=nullptr,*g_glow=nullptr,*g_btnGlow=nullptr,*g_btnGlowH=nullptr;
static ID2D1LinearGradientBrush* g_brand=nullptr,*g_green=nullptr;

enum Page { P_WELCOME, P_PREVIEW, P_THEME, P_CONFIG, P_PROGRESS, P_DONE, P_UNINSTALL, P_RETAIN };
static Page g_page = P_WELCOME;
static std::wstring g_theme=L"starlight", g_selTheme=L"", g_dir=L"", g_progText=L"准备中…", g_doneText=L"", g_uninstallDirText=L"", g_lastError=L"";
static bool g_shortcut=true, g_autostart=true, g_agree=true, g_purge=false, g_installed=false, g_showTerms=false, g_termsIsPrivacy=false, g_uninstalling=false;
static int g_pct=0;
static int g_mx=-1, g_my=-1;   // 鼠标位置（逻辑坐标，hover 跟踪）
static float g_termsScroll=0, g_termsMaxScroll=0;
static HWND g_hwnd=nullptr;

static RECT rcMin,rcClose,rcStart,rcUninstall,rcPvBack,rcPvNext,rcThBack,rcThNext,rcConfigBack,rcInstall,rcBrowse,
    rcThemeRows[3],rcChkShortcut,rcChkAutoStart,rcChkAgree,rcChkPurge,rcLinkTerms,rcLinkPrivacy,rcDone,rcLaunch,
    rcUnCancel,rcUnGo,rcRetainStay,rcRetainGo,rcRetainWeb,rcTermsClose,rcTermsModal,rcTermsPanel;

static bool Hover(const RECT& r);

struct Star{float x,y,r,a;};
static const Star kStars[]={{0.18f,0.28f,1.0f,0.70f},{0.72f,0.18f,1.0f,0.55f},{0.42f,0.62f,1.5f,0.40f},{0.86f,0.70f,1.0f,0.55f},{0.08f,0.82f,1.0f,0.35f},{0.56f,0.86f,1.5f,0.40f},{0.92f,0.42f,1.0f,0.50f},{0.30f,0.10f,1.0f,0.45f},{0.64f,0.48f,1.0f,0.30f},{0.12f,0.55f,1.0f,0.40f}};

static const wchar_t* kTerms = L"一、账号与安全\n1. 你负责自己账号的安全，请勿共享密码，发现异常及时修改。\n2. 每个账号对应独立的笔记与数据，请妥善保管登录信息。\n\n二、内容与版权\n1. 你的笔记内容归你所有（私密笔记仅自己可见；公开笔记会展示在笔记广场）。\n2. 请勿发布违反法律法规、侵犯他人权益的内容。\n\n三、AI 助手\n1. AI 生成内容仅供参考，不构成任何专业建议。\n2. AI 使用计入免费额度，超出后可前往知屿币商城兑换。\n\n四、服务说明\n1. 知屿为云端服务，数据存储于服务器，请勿存放极端敏感信息。\n2. 服务可能调整或升级，我们会尽力提前通知。\n3. 完整条款见官网：www.zhiyur.cn。";
static const wchar_t* kPrivacy = L"一、我们收集的信息\n1. 账号信息：用户名、邮箱（仅用于登录与找回）。\n2. 内容数据：你创建的笔记、收藏、批注。\n3. 使用日志：访问时间、操作记录（用于安全与优化）。\n\n二、信息的使用\n1. 仅用于提供、维护与改进知屿服务。\n2. 不会向任何第三方出售或出租你的数据。\n\n三、信息的存储与保护\n1. 数据加密存储于服务器，传输使用加密通道。\n2. 你可以随时删除自己的笔记与账号。\n\n四、你的权利\n1. 可随时导出或删除自己的数据。\n2. 对本协议有疑问可联系我们。\n3. 完整协议见官网：www.zhiyur.cn。";

static D2D1_COLOR_F Col(int rgb, float a=1.0f){ return D2D1::ColorF(((rgb>>16)&0xFF)/255.0f, ((rgb>>8)&0xFF)/255.0f, (rgb&0xFF)/255.0f, a); }
static D2D1_COLOR_F ARGB(int argb){ return D2D1::ColorF(((argb>>16)&0xFF)/255.0f, ((argb>>8)&0xFF)/255.0f, (argb&0xFF)/255.0f, ((argb>>24)&0xFF)/255.0f); }

struct AccentPolicy{int state;int flags;int color;int anim;};
struct WCAData{int attr;void* data;int size;};
static void EnableAcrylic(HWND hwnd){
    // 纯透明（不模糊）：完全禁用 accent，只靠 DirectComposition 的 alpha 合成 + 半透明背景
    HMODULE u32=LoadLibraryW(L"user32.dll");
    auto pSet=(BOOL(WINAPI*)(HWND,WCAData*))GetProcAddress(u32,"SetWindowCompositionAttribute");
    if(pSet){
        AccentPolicy ap={0,0,0,0};   // ACCENT_DISABLED
        WCAData d={19,&ap,sizeof(ap)};
        pSet(hwnd,&d);
    }
    if(u32)FreeLibrary(u32);
    HMODULE dwm=LoadLibraryW(L"dwmapi.dll");
    if(dwm){ auto pD=(HRESULT(WINAPI*)(HWND,int,LPCVOID,DWORD))GetProcAddress(dwm,"DwmSetWindowAttribute"); if(pD){int c=2;pD(hwnd,33,&c,sizeof(c));} FreeLibrary(dwm); }
}

static bool InitD2D(HWND hwnd){
    DWriteCreateFactory(DWRITE_FACTORY_TYPE_SHARED, __uuidof(IDWriteFactory), (IUnknown**)&g_dw);

    D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, D3D11_CREATE_DEVICE_BGRA_SUPPORT, nullptr, 0, D3D11_SDK_VERSION, &g_d3d, nullptr, nullptr);

    IDXGIDevice* dxgiDev = nullptr; g_d3d->QueryInterface(&dxgiDev);
    typedef HRESULT (WINAPI *FnCreateDev)(IDXGIDevice*, const D2D1_CREATION_PROPERTIES*, ID2D1Device**);
    HMODULE hD2d1 = LoadLibraryW(L"d2d1.dll");
    FnCreateDev pCreateDev = (FnCreateDev)GetProcAddress(hD2d1, "D2D1CreateDevice");
    ID2D1Device* dev = nullptr;
    D2D1_CREATION_PROPERTIES cp = { D2D1_THREADING_MODE_SINGLE_THREADED, D2D1_DEBUG_LEVEL_NONE, D2D1_DEVICE_CONTEXT_OPTIONS_NONE };
    FILE* log=fopen("d2d_diag.txt","w");
    HRESULT hr=pCreateDev(dxgiDev, &cp, &dev);
    if(log) fprintf(log,"D2D1CreateDevice=0x%08X dev=%p\n",(unsigned)hr,(void*)dev);
    dev->CreateDeviceContext(D2D1_DEVICE_CONTEXT_OPTIONS_NONE, &g_rt);
    g_rt->GetFactory(&g_factory);
    if(log) fprintf(log,"g_rt=%p\n",(void*)g_rt);
    dev->Release();

    IDXGIDevice2* dxgiDev2 = nullptr; g_d3d->QueryInterface(&dxgiDev2);
    IDXGIAdapter* adapter = nullptr; dxgiDev2->GetAdapter(&adapter);
    IDXGIFactory2* factory = nullptr; adapter->GetParent(__uuidof(IDXGIFactory2), (void**)&factory);
    DXGI_SWAP_CHAIN_DESC1 sc = {};
    sc.Width = (UINT)(W*g_scale); sc.Height = (UINT)(H*g_scale); sc.Format = DXGI_FORMAT_B8G8R8A8_UNORM;
    sc.SampleDesc.Count = 1; sc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    sc.BufferCount = 2; sc.Scaling = DXGI_SCALING_STRETCH; sc.SwapEffect = DXGI_SWAP_EFFECT_FLIP_DISCARD;
    sc.AlphaMode = DXGI_ALPHA_MODE_PREMULTIPLIED;
    hr=factory->CreateSwapChainForComposition(g_d3d, &sc, nullptr, &g_swap);
    if(log) fprintf(log,"CreateSwapChainForComposition=0x%08X swap=%p\n",(unsigned)hr,(void*)g_swap);
    factory->Release(); adapter->Release(); dxgiDev2->Release();

    hr=DCompositionCreateDevice(dxgiDev, __uuidof(IDCompositionDevice), (void**)&g_dcomp);
    if(log) fprintf(log,"DCompositionCreateDevice=0x%08X\n",(unsigned)hr);
    g_dcomp->CreateTargetForHwnd(hwnd, TRUE, &g_dcompTarget);
    g_dcomp->CreateVisual(&g_dcompVisual);
    g_dcompVisual->SetContent(g_swap);
    g_dcompTarget->SetRoot(g_dcompVisual);
    g_dcomp->Commit();
    dxgiDev->Release();

    IDXGISurface* surface = nullptr; g_swap->GetBuffer(0, __uuidof(IDXGISurface), (void**)&surface);
    D2D1_BITMAP_PROPERTIES1 bp = D2D1::BitmapProperties1(D2D1_BITMAP_OPTIONS_TARGET | D2D1_BITMAP_OPTIONS_CANNOT_DRAW, D2D1::PixelFormat(DXGI_FORMAT_B8G8R8A8_UNORM, D2D1_ALPHA_MODE_PREMULTIPLIED));
    hr=g_rt->CreateBitmapFromDxgiSurface(surface, &bp, &g_target);
    if(log) fprintf(log,"CreateBitmapFromDxgiSurface=0x%08X target=%p\n",(unsigned)hr,(void*)g_target);
    surface->Release();
    g_rt->SetTarget(g_target);
    if(log) fclose(log);

    HDC hdc=GetDC(hwnd); int dpi=GetDeviceCaps(hdc,LOGPIXELSX); ReleaseDC(hwnd,hdc);
    g_rt->SetDpi((float)dpi,(float)dpi);
    g_rt->SetTextAntialiasMode(D2D1_TEXT_ANTIALIAS_MODE_GRAYSCALE);
    g_factory->CreateRoundedRectangleGeometry(D2D1::RoundedRect(D2D1::RectF(0,0,W,H),16,16), &g_clipGeo);
    D2D1_STROKE_STYLE_PROPERTIES sp = D2D1::StrokeStyleProperties(D2D1_CAP_STYLE_ROUND, D2D1_CAP_STYLE_ROUND, D2D1_CAP_STYLE_ROUND, D2D1_LINE_JOIN_ROUND, 10.0f, D2D1_DASH_STYLE_SOLID, 0.0f);
    g_factory->CreateStrokeStyle(sp, nullptr, 0, &g_stroke);

    g_rt->CreateSolidColorBrush(D2D1::ColorF(1,1,1), &g_white);
    g_rt->CreateSolidColorBrush(ARGB(0xE6E8ECF8), &g_text);
    g_rt->CreateSolidColorBrush(ARGB(0x9EE8ECF8), &g_dim);
    g_rt->CreateSolidColorBrush(Col(0xF87171), &g_red);
    g_rt->CreateSolidColorBrush(Col(0xE5484D), &g_closeRed);
    g_rt->CreateSolidColorBrush(Col(0x3B82F6), &g_blue);
    g_rt->CreateSolidColorBrush(Col(0x93C5FD), &g_blueGlow);
    g_rt->CreateSolidColorBrush(Col(0x60A5FA), &g_shadow);
    g_rt->CreateSolidColorBrush(D2D1::ColorF(1,1,1,0.15f), &g_card);         // #26FFFFFF
    g_rt->CreateSolidColorBrush(D2D1::ColorF(1,1,1,0.20f), &g_cardBorder);   // #33FFFFFF
    g_rt->CreateSolidColorBrush(D2D1::ColorF(1,1,1,0.06f), &g_ghost);        // #0FFFFFFF
    g_rt->CreateSolidColorBrush(D2D1::ColorF(1,1,1,0.12f), &g_border);       // #1FFFFFFF
    g_rt->CreateSolidColorBrush(D2D1::ColorF(1,1,1,0.05f), &g_themeRow);     // #0DFFFFFF
    g_rt->CreateSolidColorBrush(D2D1::ColorF(1,1,1,0.10f), &g_titleHover);   // #1AFFFFFF 标题栏按钮 hover
    g_rt->CreateSolidColorBrush(ARGB(0x1F3B82F6), &g_themeHover);            // 主题行 hover
    g_rt->CreateSolidColorBrush(ARGB(0x3FFFFFFF), &g_chkBorder);             // 复选边框
    g_rt->CreateSolidColorBrush(ARGB(0x143B82F6), &g_progressBg);            // 进度条底
    g_rt->CreateSolidColorBrush(ARGB(0x29EF4444), &g_redBg);                 // 危险按钮底
    g_rt->CreateSolidColorBrush(ARGB(0x47EF4444), &g_redBgH);                // 危险按钮 hover
    g_rt->CreateSolidColorBrush(ARGB(0x59EF4444), &g_redBorder);             // 危险按钮边框
    g_rt->CreateSolidColorBrush(ARGB(0x99020617), &g_overlay);               // 弹窗遮罩
    g_rt->CreateSolidColorBrush(ARGB(0xEB0F172A), &g_modalBg);               // 弹窗面板
    g_rt->CreateSolidColorBrush(ARGB(0x1A3B82F6), &g_blueTint);              // 网页版按钮底
    g_rt->CreateSolidColorBrush(ARGB(0x383B82F6), &g_blueTintH);             // 网页版按钮底 hover
    {
        D2D1_GRADIENT_STOP s[3]={{0,ARGB(0x473B82F6)},{0.55f,ARGB(0xD10F172A)},{1,ARGB(0xE6020617)}};
        ID2D1GradientStopCollection* sc; g_rt->CreateGradientStopCollection(s,3,&sc);
        g_rt->CreateRadialGradientBrush(D2D1::RadialGradientBrushProperties(D2D1::Point2F(W*0.2f,0),D2D1::Point2F(0,0),W*1.2f,H*1.2f),sc,&g_bg); sc->Release();
    }
    { D2D1_GRADIENT_STOP s[2]={{0,ARGB(0x593B82F6)},{1,ARGB(0x003B82F6)}}; ID2D1GradientStopCollection* sc; g_rt->CreateGradientStopCollection(s,2,&sc); g_rt->CreateRadialGradientBrush(D2D1::RadialGradientBrushProperties(D2D1::Point2F(W-110,70),D2D1::Point2F(0,0),190,190),sc,&g_glow); sc->Release(); }
    { D2D1_GRADIENT_STOP s[2]={{0,Col(0x3B82F6)},{1,Col(0x2563EB)}}; ID2D1GradientStopCollection* sc; g_rt->CreateGradientStopCollection(s,2,&sc); g_rt->CreateLinearGradientBrush(D2D1::LinearGradientBrushProperties(D2D1::Point2F(0,0),D2D1::Point2F(1,1)),sc,&g_brand); sc->Release(); }
    { D2D1_GRADIENT_STOP s[2]={{0,Col(0x22C55E)},{1,Col(0x16A34A)}}; ID2D1GradientStopCollection* sc; g_rt->CreateGradientStopCollection(s,2,&sc); g_rt->CreateLinearGradientBrush(D2D1::LinearGradientBrushProperties(D2D1::Point2F(0,0),D2D1::Point2F(1,1)),sc,&g_green); sc->Release(); }
    { D2D1_GRADIENT_STOP s[2]={{0,ARGB(0x4060A5FA)},{1,ARGB(0x0060A5FA)}}; ID2D1GradientStopCollection* sc; g_rt->CreateGradientStopCollection(s,2,&sc); g_rt->CreateRadialGradientBrush(D2D1::RadialGradientBrushProperties(D2D1::Point2F(0,0),D2D1::Point2F(0,0),1,1),sc,&g_btnGlow); sc->Release(); }
    { D2D1_GRADIENT_STOP s[2]={{0,ARGB(0x5093C5FD)},{1,ARGB(0x0093C5FD)}}; ID2D1GradientStopCollection* sc; g_rt->CreateGradientStopCollection(s,2,&sc); g_rt->CreateRadialGradientBrush(D2D1::RadialGradientBrushProperties(D2D1::Point2F(0,0),D2D1::Point2F(0,0),1,1),sc,&g_btnGlowH); sc->Release(); }
    auto mk=[&](IDWriteTextFormat** f, DWRITE_FONT_WEIGHT w, float sz, DWRITE_TEXT_ALIGNMENT al=DWRITE_TEXT_ALIGNMENT_CENTER){ g_dw->CreateTextFormat(L"Segoe UI",nullptr,w,DWRITE_FONT_STYLE_NORMAL,DWRITE_FONT_STRETCH_NORMAL,sz,L"zh-cn",f); (*f)->SetTextAlignment(al); };
    mk(&f_title,DWRITE_FONT_WEIGHT_BLACK,42);
    mk(&f_check,DWRITE_FONT_WEIGHT_BLACK,34);
    mk(&f_h1_26,DWRITE_FONT_WEIGHT_BLACK,26);
    mk(&f_h1,DWRITE_FONT_WEIGHT_BLACK,24);
    mk(&f_h1L,DWRITE_FONT_WEIGHT_BLACK,24,DWRITE_TEXT_ALIGNMENT_LEADING);
    mk(&f_h2,DWRITE_FONT_WEIGHT_BLACK,22);
    mk(&f_body,DWRITE_FONT_WEIGHT_NORMAL,17);
    mk(&f_btn,DWRITE_FONT_WEIGHT_BOLD,15);
    mk(&f_btnGhost,DWRITE_FONT_WEIGHT_NORMAL,14);
    mk(&f_btnDanger,DWRITE_FONT_WEIGHT_BOLD,14);
    mk(&f_tb,DWRITE_FONT_WEIGHT_NORMAL,12);
    mk(&f_name,DWRITE_FONT_WEIGHT_BOLD,13,DWRITE_TEXT_ALIGNMENT_LEADING);
    mk(&f_label,DWRITE_FONT_WEIGHT_NORMAL,13.5,DWRITE_TEXT_ALIGNMENT_LEADING);
    mk(&f_labelC,DWRITE_FONT_WEIGHT_NORMAL,13.5);
    mk(&f_sub,DWRITE_FONT_WEIGHT_NORMAL,13,DWRITE_TEXT_ALIGNMENT_LEADING);
    mk(&f_subC,DWRITE_FONT_WEIGHT_NORMAL,13);
    mk(&f_cardName,DWRITE_FONT_WEIGHT_BOLD,14.5,DWRITE_TEXT_ALIGNMENT_LEADING);
    mk(&f_small,DWRITE_FONT_WEIGHT_NORMAL,12,DWRITE_TEXT_ALIGNMENT_LEADING);
    mk(&f_themeDesc,DWRITE_FONT_WEIGHT_NORMAL,12.5,DWRITE_TEXT_ALIGNMENT_LEADING);
    mk(&f_themeName,DWRITE_FONT_WEIGHT_BOLD,16,DWRITE_TEXT_ALIGNMENT_LEADING);
    mk(&f_badge,DWRITE_FONT_WEIGHT_BOLD,10.5);
    mk(&f_termsTitle,DWRITE_FONT_WEIGHT_BOLD,15,DWRITE_TEXT_ALIGNMENT_LEADING);
    g_dw->CreateTextFormat(L"Segoe UI Emoji",nullptr,DWRITE_FONT_WEIGHT_NORMAL,DWRITE_FONT_STYLE_NORMAL,DWRITE_FONT_STRETCH_NORMAL,20,L"zh-cn",&f_emoji); f_emoji->SetTextAlignment(DWRITE_TEXT_ALIGNMENT_CENTER);
    return true;
}

static void Txt(const wchar_t* s, IDWriteTextFormat* f, ID2D1Brush* b, float x, float y, float w, float h){ if(s&&*s) g_rt->DrawTextW(s,(UINT32)wcslen(s),f,D2D1::RectF(x,y,x+w,y+h),b); }
static void RRect(float l,float t,float r,float b,float rad,ID2D1Brush* brush,float sw=0,ID2D1Brush* stroke=nullptr){ D2D1_ROUNDED_RECT rr=D2D1::RoundedRect(D2D1::RectF(l,t,r,b),rad,rad); g_rt->FillRoundedRectangle(rr,brush); if(stroke) g_rt->DrawRoundedRectangle(rr,stroke,sw); }
static void GradRect(float l,float t,float r,float b,float rad,ID2D1LinearGradientBrush* brush){
    brush->SetStartPoint(D2D1::Point2F(l,t));
    brush->SetEndPoint(D2D1::Point2F(r,b));
    RRect(l,t,r,b,rad,brush);
}
static float Measure(const wchar_t* s, IDWriteTextFormat* f){
    if(!s||!*s) return 0;
    IDWriteTextLayout* ly=nullptr;
    if(FAILED(g_dw->CreateTextLayout(s,(UINT32)wcslen(s),f,10000,10000,&ly))) return 0;
    DWRITE_TEXT_METRICS m{}; ly->GetMetrics(&m);
    float w=m.widthIncludingTrailingWhitespace; ly->Release(); return w;
}
static float BtnW(const wchar_t* txt, IDWriteTextFormat* f, float pad){ return Measure(txt,f)+2*pad; }

// 幽灵按钮（hover 变亮 #1FFFFFFF）
static void GhostBtn(float l,float t,float r,float b,const wchar_t* txt,const RECT& rc){
    bool h=Hover(rc);
    RRect(l,t,r,b,22,h?g_border:g_ghost,1,g_border);
    Txt(txt,f_btnGhost,g_text,l,t+12,r-l,22);
}
// 主按钮（hover 上浮 1px）
static void PrimaryBtn(float l,float t,float r,float b,const wchar_t* txt,const RECT& rc){
    bool h=Hover(rc);
    float tt=h?t-1:t, bb=h?b-1:b;
    float cx=(l+r)/2, cy=(tt+bb)/2, gy=cy+(h?12:8);
    ID2D1RadialGradientBrush* glow=h?g_btnGlowH:g_btnGlow;
    float rx=(r-l)/2+(h?24:18), ry=(bb-tt)/2+(h?26:20);
    glow->SetCenter(D2D1::Point2F(cx,gy));
    glow->SetGradientOriginOffset(D2D1::Point2F(0,0));
    glow->SetRadiusX(rx); glow->SetRadiusY(ry);
    g_rt->FillEllipse(D2D1::Ellipse(D2D1::Point2F(cx,gy),rx,ry),glow);
    g_brand->SetStartPoint(D2D1::Point2F(l,tt));
    g_brand->SetEndPoint(D2D1::Point2F(r,bb));
    RRect(l,tt,r,bb,22,g_brand);
    Txt(txt,f_btn,g_white,l,tt+12,r-l,22);
}
// 危险按钮（卸载，hover 变亮）
static void DangerBtn(float l,float t,float r,float b,const wchar_t* txt,const RECT& rc){
    bool h=Hover(rc);
    RRect(l,t,r,b,22,h?g_redBgH:g_redBg,1,g_redBorder);
    Txt(txt,f_btnDanger,g_red,l,t+12,r-l,22);
}
// 勾选复选框
static void CheckBox(float l,float t,bool c,const wchar_t* label,ID2D1Brush* lb){
    if(c){ RRect(l,t,l+16,t+16,4,g_blue,1,g_blue); Txt(L"✓",f_name,g_white,l,t-1,16,18); }
    else { g_rt->DrawRoundedRectangle(D2D1::RoundedRect(D2D1::RectF(l,t,l+16,t+16),4,4), g_chkBorder, 1.0f); }
    if(label&&*label) Txt(label,f_label,lb,l+24,t-2,Measure(label,f_label)+4,20);
}

// 圆弧 → 三次贝塞尔段（稳健复刻 C# 的 A 命令，避免 AddArc 半圆边界问题；结果与 C# Path 完全一致）
static void ArcBezier(ID2D1GeometrySink* sink, float cx,float cy,float s, float x1,float y1,float x2,float y2,float r,bool largeArc,bool sweep){
    const float PI=3.14159265358979f;
    auto P=[&](float x,float y){ return D2D1::Point2F(cx+(x-32)*s, cy+(y-32)*s); };
    float x1p=(x1-x2)/2, y1p=(y1-y2)/2;
    float rr=r*r, dd=x1p*x1p+y1p*y1p;
    if(dd>rr){ float sc=sqrtf(dd/rr); r*=sc; rr=r*r; }
    float rad=(rr-dd)/dd; if(rad<0) rad=0;
    float coef=sqrtf(rad);
    if(largeArc==sweep) coef=-coef;
    float cxp=coef*y1p, cyp=-coef*x1p;
    float ccx=(x1+x2)/2+cxp, ccy=(y1+y2)/2+cyp;
    auto vangle=[&](float ux,float uy,float vx,float vy){
        float dot=ux*vx+uy*vy, len=sqrtf((ux*ux+uy*uy)*(vx*vx+vy*vy));
        if(len<=0) return 0.0f;
        float t=dot/len; if(t>1.0f)t=1.0f; if(t<-1.0f)t=-1.0f;
        float a=acosf(t);
        return (ux*vy-uy*vx<0)?-a:a;
    };
    float ux=(x1p-cxp)/r, uy=(y1p-cyp)/r;
    float vx=(-x1p-cxp)/r, vy=(-y1p-cyp)/r;
    float th1=vangle(1,0,ux,uy);
    float dth=vangle(ux,uy,vx,vy);
    if(!sweep && dth>0) dth-=2*PI;
    if(sweep && dth<0) dth+=2*PI;
    int n=(int)ceilf(fabsf(dth)/(PI/2)); if(n<1)n=1;
    float seg=dth/n;
    for(int i=0;i<n;i++){
        float a0=th1+i*seg, a1=a0+seg;
        float k=(4.0f/3.0f)*tanf(seg/4.0f);
        float q0x=ccx+r*cosf(a0), q0y=ccy+r*sinf(a0);
        float q1x=ccx+r*cosf(a1), q1y=ccy+r*sinf(a1);
        sink->AddBezier(D2D1_BEZIER_SEGMENT{
            P(q0x+k*(-r*sinf(a0)), q0y+k*(r*cosf(a0))),
            P(q1x-k*(-r*sinf(a1)), q1y-k*(r*cosf(a1))),
            P(q1x,q1y)});
    }
}
// 勾形 logo（精确复刻 C# Path：M31 7 C 37 7,39 11,34 16 A 10 10 0 0 0 34 36 A 16 16 0 0 0 34 58 A 16 16 0 0 0 34 26）
static void DrawLogo(float cx,float cy,float size){
    float s=size/64.0f;
    auto P=[&](float x,float y){ return D2D1::Point2F(cx+(x-32)*s, cy+(y-32)*s); };
    ID2D1PathGeometry* geo; g_factory->CreatePathGeometry(&geo);
    ID2D1GeometrySink* sink; geo->Open(&sink);
    sink->BeginFigure(P(31,7), D2D1_FIGURE_BEGIN_HOLLOW);
    sink->AddBezier(D2D1_BEZIER_SEGMENT{P(37,7), P(39,11), P(34,16)});
    ArcBezier(sink,cx,cy,s, 34,16, 34,36, 10, false, false);
    ArcBezier(sink,cx,cy,s, 34,36, 34,58, 16, false, false);
    ArcBezier(sink,cx,cy,s, 34,58, 34,26, 16, false, false);
    sink->EndFigure(D2D1_FIGURE_END_OPEN);
    sink->Close(); sink->Release();
    g_rt->SetAntialiasMode(D2D1_ANTIALIAS_MODE_PER_PRIMITIVE);
    g_rt->DrawGeometry(geo, g_white, 7*s, g_stroke);
    geo->Release();
}

// 页面内容区：上 64 / 下 564（标题栏 44 + 上下 margin）
static float VTop(float totalH){ return 64.0f + (500.0f - totalH)/2.0f; }

static void DrawWelcome(){
    float cx=430;
    float total = g_installed ? 388.0f : 330.0f;
    float y = VTop(total);
    // 图标 84x84
    GradRect(cx-42,y,cx+42,y+84,24,g_brand);
    DrawLogo(cx,y+42,46);
    // 标题行（知屿 + ✦，整体水平居中）
    float titleW=Measure(L"知屿",f_title);
    float starW=Measure(L"✦",f_h2);
    float rowW=titleW+2+starW;
    float rowL=cx-rowW/2, rowT=y+84+18;
    Txt(L"知屿",f_title,g_white,rowL,rowT,titleW,52);
    float sx=rowL+titleW+2, sy=rowT+6;
    float gx=sx+starW/2, gy=sy+11;
    g_btnGlowH->SetCenter(D2D1::Point2F(gx,gy));
    g_btnGlowH->SetGradientOriginOffset(D2D1::Point2F(0,0));
    g_btnGlowH->SetRadiusX(24); g_btnGlowH->SetRadiusY(24);
    g_btnGlowH->SetOpacity(0.4f);
    g_rt->FillEllipse(D2D1::Ellipse(D2D1::Point2F(gx,gy),24,24),g_btnGlowH);
    g_btnGlowH->SetOpacity(1.0f);
    Txt(L"✦",f_h2,g_blueGlow,sx,sy,starW,28);
    y=rowT+52+14;
    Txt(L"把散落的笔记、截图与灵感，",f_body,g_text,cx-280,y,560,30);
    Txt(L"汇成一座属于自己的知识岛。",f_body,g_text,cx-280,y+30,560,30);
    y+=60+8;
    Txt(L"个人知识库 · 笔记 / 截图 / AI 助手 / 收藏，云端同步，随处访问。",f_subC,g_dim,cx-280,y,560,20);
    y+=20+30;
    float bw=BtnW(L"开始安装 →",f_btn,38);
    rcStart={(LONG)(cx-bw/2),(LONG)y,(LONG)(cx+bw/2),(LONG)(y+44)};
    PrimaryBtn(cx-bw/2,y,cx+bw/2,y+44,L"开始安装 →",rcStart);
    if(g_installed){
        y+=44+14;
        float uw=BtnW(L"卸载知屿",f_btnDanger,26);
        rcUninstall={(LONG)(cx-uw/2),(LONG)y,(LONG)(cx+uw/2),(LONG)(y+44)};
        DangerBtn(cx-uw/2,y,cx+uw/2,y+44,L"卸载知屿",rcUninstall);
    }
}

static void FeatCard(float l,float t,float r,float b,const wchar_t* emoji,int c1,int c2,const wchar_t* name,const wchar_t* desc){
    bool h=(g_mx>=l&&g_mx<=r&&g_my>=t&&g_my<=b);
    float tt=h?t-2:t, bb=h?b-2:b;
    RRect(l,tt,r,bb,16,h?g_titleHover:g_card,1,g_cardBorder);
    ID2D1LinearGradientBrush* g=nullptr; ID2D1GradientStopCollection* sc=nullptr;
    D2D1_GRADIENT_STOP s[2]={{0,Col(c1)},{1,Col(c2)}};
    g_rt->CreateGradientStopCollection(s,2,&sc);
    g_rt->CreateLinearGradientBrush(D2D1::LinearGradientBrushProperties(D2D1::Point2F(l+16,tt+16),D2D1::Point2F(l+60,tt+60)),sc,&g);
    RRect(l+16,tt+16,l+60,tt+60,12,g);
    Txt(emoji,f_emoji,g_white,l+16,tt+24,44,28);
    Txt(name,f_cardName,g_white,l+16,tt+68,r-l-32,18);
    g_rt->DrawTextW(desc,(UINT32)wcslen(desc),f_small,D2D1::RectF(l+16,tt+91,r-16,tt+129),g_dim);
    sc->Release(); g->Release();
}
static void DrawPreview(){
    float cx=430, L=48, R=812, CW=764;
    float cardW=(CW-2*14)/3, cardH=145, rowGap=14;
    float total=60+22+(cardH*2+rowGap)+30+44; // 460
    float top=VTop(total);
    // 头部（logo 60x60 + 标题）
    float titleW=Measure(L"一座知识岛，装下你的一切",f_h2);
    float subW=Measure(L"笔记、截图、灵感、AI，全都安放在一起。",f_sub);
    float hw=60+16+(titleW>subW?titleW:subW);
    float hl=cx-hw/2;
    GradRect(hl,top,hl+60,top+60,17,g_brand);
    DrawLogo(hl+30,top+30,34);
    Txt(L"一座知识岛，装下你的一切",f_h2,g_white,hl+76,top+2,titleW,28);
    Txt(L"笔记、截图、灵感、AI，全都安放在一起。",f_sub,g_dim,hl+76,top+36,subW,18);
    // 卡片 3x2
    float gy=top+60+22;
    struct F{const wchar_t* e;int a;int b;const wchar_t* n;const wchar_t* d;} fs[6]={
        {L"📝",0x3B82F6,0x2563EB,L"Markdown 笔记",L"代码高亮、公式渲染、自定义容器，把笔记写得漂亮。"},
        {L"✂️",0xF59E0B,0xD97706,L"截图与附件",L"粘贴即存、图片可拉伸标注，灵感随手收下。"},
        {L"🤖",0x8B5CF6,0x6D28D9,L"AI 助手",L"DeepSeek 驱动：问答、总结、辅助写作，随叫随到。"},
        {L"⛅",0x0EA5E9,0x0284C7,L"云端同步",L"网页 / 桌面多端登录，笔记随时随取。"},
        {L"📚",0x10B981,0x059669,L"阅览室与广场",L"收藏、阅读、分享，构建自己的知识体系。"},
        {L"🎨",0xEC4899,0xDB2777,L"多主题界面",L"深空星际 / 晴空 / 简约，风格随你切换。"},
    };
    for(int i=0;i<6;i++){ int c=i%3,r=i/3; float l=L+c*(cardW+14), t=gy+r*(cardH+rowGap); FeatCard(l,t,l+cardW,t+cardH,fs[i].e,fs[i].a,fs[i].b,fs[i].n,fs[i].d); }
    float by=gy+(cardH*2+rowGap)+30;
    float bw=BtnW(L"← 上一步",f_btnGhost,26);
    rcPvBack={(LONG)L,(LONG)by,(LONG)(L+bw),(LONG)(by+44)};
    GhostBtn(L,by,L+bw,by+44,L"← 上一步",rcPvBack);
    float nw=BtnW(L"下一步：选择主题 →",f_btn,38);
    rcPvNext={(LONG)(R-nw),(LONG)by,(LONG)R,(LONG)(by+44)};
    PrimaryBtn(R-nw,by,R,by+44,L"下一步：选择主题 →",rcPvNext);
}

static void ThemeRow(float l,float t,float r,float b,const wchar_t* name,const wchar_t* desc,int c1,int c2,bool sel,bool def){
    bool h=(g_mx>=l&&g_mx<=r&&g_my>=t&&g_my<=b);
    float ll=h?l+3:l;
    ID2D1Brush* bg=h?g_themeHover:g_themeRow;
    ID2D1Brush* bd=(sel||h)?(ID2D1Brush*)g_blue:(ID2D1Brush*)g_themeRow;
    float sw=(sel||h)?2.0f:1.0f;
    RRect(ll,t,r,b,16,bg,sw,bd);
    float nx=ll+16;
    Txt(name,f_themeName,g_white,nx,t+14,Measure(name,f_themeName),20);
    float nw=Measure(name,f_themeName);
    if(def){
        float bw=Measure(L"默认",f_badge)+16;
        RRect(nx+nw+6,t+15,nx+nw+6+bw,t+33,8,g_blue);
        Txt(L"默认",f_badge,g_white,nx+nw+6,t+16,bw,16);
    }
    Txt(desc,f_themeDesc,g_dim,nx,t+41,r-l-190,18);
    ID2D1LinearGradientBrush* g=nullptr; ID2D1GradientStopCollection* sc=nullptr;
    D2D1_GRADIENT_STOP s[2]={{0,Col(c1)},{1,Col(c2)}};
    g_rt->CreateGradientStopCollection(s,2,&sc);
    g_rt->CreateLinearGradientBrush(D2D1::LinearGradientBrushProperties(D2D1::Point2F(r-170,t+12),D2D1::Point2F(r-20,t+64)),sc,&g);
    RRect(r-170,t+12,r-20,t+64,9,g,1,g_border);
    sc->Release(); g->Release();
}
static void DrawTheme(){
    float cx=430, L=cx-280, R=cx+280, rh=78;
    float total=32+10+18+20+(rh*3+14*2)+30+44; // 416
    float y=VTop(total);
    Txt(L"选择你的主题",f_h1L,g_white,L,y,560,32);
    y+=32+10;
    Txt(L"安装后默认使用，随时可在设置里切换。",f_sub,g_dim,L,y,560,18);
    y+=18+20;
    ThemeRow(L,y,R,y+rh,L"深空星际",L"深邃蓝紫夜空，沉浸式阅读，暗光环境更护眼。",0x0B1226,0x1E3A8A,g_selTheme==L"starlight",true); rcThemeRows[0]={(LONG)L,(LONG)y,(LONG)R,(LONG)(y+rh)};
    y+=rh+14;
    ThemeRow(L,y,R,y+rh,L"晴空",L"清爽浅蓝天空，明亮通透，白天用着舒服。",0xE8F4FF,0x7DB9F0,g_selTheme==L"sky",false); rcThemeRows[1]={(LONG)L,(LONG)y,(LONG)R,(LONG)(y+rh)};
    y+=rh+14;
    ThemeRow(L,y,R,y+rh,L"简约",L"干净灰白，少干扰，专注内容本身。",0xF5F5F5,0xE0E0E0,g_selTheme==L"minimal",false); rcThemeRows[2]={(LONG)L,(LONG)y,(LONG)R,(LONG)(y+rh)};
    y+=rh+30;
    float bw=BtnW(L"← 上一步",f_btnGhost,26);
    rcThBack={(LONG)L,(LONG)y,(LONG)(L+bw),(LONG)(y+44)}; GhostBtn(L,y,L+bw,y+44,L"← 上一步",rcThBack);
    float nw=BtnW(L"下一步 →",f_btn,38);
    rcThNext={(LONG)(R-nw),(LONG)y,(LONG)R,(LONG)(y+44)}; PrimaryBtn(R-nw,y,R,y+44,L"下一步 →",rcThNext);
}

static void DrawConfig(){
    float cx=430, L=cx-280, R=cx+280;
    float total=32+20+18+10+44+24+20+14+20+30+44; // 276
    float y=VTop(total);
    Txt(L"安装配置",f_h1L,g_white,L,y,560,32);
    y+=32+20;
    Txt(L"安装位置",f_sub,g_dim,L,y,560,18);
    y+=18+10;
    float bw=BtnW(L"浏览…",f_btnGhost,26);
    RRect(L,y,R-bw-10,y+44,10,g_ghost,1,g_border);
    Txt(g_dir.c_str(),f_sub,g_text,L+14,y+12,R-L-14-bw-10-8,20);
    rcBrowse={(LONG)(R-bw),(LONG)y,(LONG)R,(LONG)(y+44)}; GhostBtn(R-bw,y,R,y+44,L"浏览…",rcBrowse);
    y+=44+24;
    float cw1=24+Measure(L"创建桌面快捷方式",f_label);
    float cw2=24+Measure(L"开机自启动",f_label);
    CheckBox(L,y,g_shortcut,L"创建桌面快捷方式",g_text); rcChkShortcut={(LONG)L,(LONG)y,(LONG)(L+cw1),(LONG)(y+20)};
    float ax=L+cw1+26;
    CheckBox(ax,y,g_autostart,L"开机自启动",g_text); rcChkAutoStart={(LONG)ax,(LONG)y,(LONG)(ax+cw2),(LONG)(y+20)};
    y+=20+14;
    CheckBox(L,y,g_agree,nullptr,g_text); rcChkAgree={(LONG)L,(LONG)y,(LONG)(L+16),(LONG)(y+20)};
    float tx=L+24;
    // 单个 TextLayout 保证与 C# 完全一致的字间距，链接段蓝色 + 下划线
    const wchar_t* agreeTxt=L"我已阅读并同意《服务条款》和《隐私协议》";
    IDWriteTextLayout* al=nullptr;
    g_dw->CreateTextLayout(agreeTxt,(UINT32)wcslen(agreeTxt),f_label,10000,10000,&al);
    DWRITE_TEXT_RANGE r1={7,6}, r2={14,6};
    al->SetUnderline(TRUE, r1); al->SetUnderline(TRUE, r2);
    g_rt->DrawTextLayout(D2D1::Point2F(tx,y-1), al, g_text);
    float m1=Measure(L"我已阅读并同意",f_label);
    float m2=Measure(L"《服务条款》",f_label);
    float m3=Measure(L"和",f_label);
    float m4=Measure(L"《隐私协议》",f_label);
    rcLinkTerms={(LONG)(tx+m1),(LONG)y,(LONG)(tx+m1+m2),(LONG)(y+20)};
    rcLinkPrivacy={(LONG)(tx+m1+m2+m3),(LONG)y,(LONG)(tx+m1+m2+m3+m4),(LONG)(y+20)};
    for(int k=0;k<2;k++){
        DWRITE_TEXT_RANGE r=k==0?r1:r2;
        UINT32 hitN=0;
        al->HitTestTextRange(r.startPosition,r.length,0,0,nullptr,0,&hitN);
        if(hitN>0){
            std::vector<DWRITE_HIT_TEST_METRICS> hits(hitN);
            al->HitTestTextRange(r.startPosition,r.length,0,0,hits.data(),hitN,&hitN);
            for(UINT32 i=0;i<hitN;i++){
                DWRITE_HIT_TEST_METRICS& hh=hits[i];
                g_rt->PushAxisAlignedClip(D2D1::RectF(tx+hh.left, y-1+hh.top, tx+hh.left+hh.width, y-1+hh.top+hh.height), D2D1_ANTIALIAS_MODE_ALIASED);
                g_rt->DrawTextLayout(D2D1::Point2F(tx,y-1), al, g_blue);
                g_rt->PopAxisAlignedClip();
            }
        }
    }
    al->Release();
    y+=20+30;
    float bb=BtnW(L"← 上一步",f_btnGhost,26);
    rcConfigBack={(LONG)L,(LONG)y,(LONG)(L+bb),(LONG)(y+44)}; GhostBtn(L,y,L+bb,y+44,L"← 上一步",rcConfigBack);
    float iw=BtnW(L"安装",f_btn,38);
    rcInstall={(LONG)(R-iw),(LONG)y,(LONG)R,(LONG)(y+44)}; PrimaryBtn(R-iw,y,R,y+44,L"安装",rcInstall);
}

static void DrawProgress(){
    float cx=430, L=150, R=710;
    float total=28+28+14+16+18+6+28; // 138
    float y=VTop(total);
    Txt(g_uninstalling?L"正在卸载":L"正在安装",f_h2,g_white,cx-280,y,560,28);
    y+=28+28;
    RRect(L,y,R,y+14,7,g_progressBg,1,g_border);
    float pw=(R-L)*g_pct/100.0f; if(pw>0) GradRect(L,y,L+pw,y+14,7,g_brand);
    y+=14+16;
    Txt(g_progText.c_str(),f_labelC,g_dim,L,y,560,18);
    y+=18+6;
    Txt((std::to_wstring(g_pct)+L"%").c_str(),f_h2,g_white,L,y,560,28);
}

static void DrawDone(){
    float cx=430;
    float total=76+16+34+12+18+26+44; // 226
    float y=VTop(total);
    GradRect(cx-38,y,cx+38,y+76,38,g_green);
    Txt(L"✓",f_check,g_white,cx-30,y+17,60,42);
    y+=76+16;
    Txt(g_uninstalling?L"卸载完成":L"安装完成",f_h1_26,g_white,cx-280,y,560,34);
    y+=34+12;
    Txt(g_doneText.c_str(),f_labelC,g_dim,cx-280,y,560,18);
    y+=18+26;
    if(g_uninstalling){
        float bw=BtnW(L"完成",f_btnGhost,26);
        rcDone={(LONG)(cx-bw/2),(LONG)y,(LONG)(cx+bw/2),(LONG)(y+44)}; GhostBtn(cx-bw/2,y,cx+bw/2,y+44,L"完成",rcDone);
        rcLaunch={0,0,0,0};
    } else {
        float bw=BtnW(L"完成",f_btnGhost,26);
        float lw=BtnW(L"启动知屿",f_btn,38);
        float l0=cx-(bw+12+lw)/2;
        rcDone={(LONG)l0,(LONG)y,(LONG)(l0+bw),(LONG)(y+44)}; GhostBtn(l0,y,l0+bw,y+44,L"完成",rcDone);
        rcLaunch={(LONG)(l0+bw+12),(LONG)y,(LONG)(l0+bw+12+lw),(LONG)(y+44)}; PrimaryBtn(l0+bw+12,y,l0+bw+12+lw,y+44,L"启动知屿",rcLaunch);
    }
}

static void DrawUninstall(){
    float cx=430;
    float total=72+16+34+12+18+8+18+20+20+30+44; // 292
    float y=VTop(total);
    GradRect(cx-36,y,cx+36,y+72,20,g_brand);
    DrawLogo(cx,y+36,40);
    y+=72+16;
    Txt(L"卸载知屿？",f_h1_26,g_white,cx-280,y,560,34);
    y+=34+12;
    Txt(g_uninstallDirText.c_str(),f_labelC,g_dim,cx-280,y,560,18);
    y+=18+8;
    Txt(L"你的云端笔记数据不受影响（保存在服务器）。",f_subC,g_dim,cx-280,y,560,18);
    y+=18+20;
    float labW=Measure(L"同时删除本地个人数据（登录状态、主题设置）",f_label);
    float chkW=16+8+labW;
    float cl=cx-chkW/2;
    CheckBox(cl,y,g_purge,L"同时删除本地个人数据（登录状态、主题设置）",g_text);
    rcChkPurge={(LONG)cl,(LONG)y,(LONG)(cl+chkW),(LONG)(y+20)};
    y+=20+30;
    float gl=cx-210, gr=cx+210;
    float bw=BtnW(L"取消",f_btnGhost,26);
    float dw=BtnW(L"继续卸载",f_btnDanger,26);
    rcUnCancel={(LONG)gl,(LONG)y,(LONG)(gl+bw),(LONG)(y+44)}; GhostBtn(gl,y,gl+bw,y+44,L"取消",rcUnCancel);
    rcUnGo={(LONG)(gr-dw),(LONG)y,(LONG)gr,(LONG)(y+44)}; DangerBtn(gr-dw,y,gr,y+44,L"继续卸载",rcUnGo);
}

// ── 挽留页 ──
static void DrawRetain(){
    float cx=430;
    float total=72+16+34+12+18+6+18+30+44+24+40; // 314
    float y=VTop(total);
    GradRect(cx-36,y,cx+36,y+72,20,g_brand);
    DrawLogo(cx,y+36,40);
    y+=72+16;
    Txt(L"真的要离开吗？",f_h1_26,g_white,cx-280,y,560,34);
    y+=34+12;
    Txt(L"你的笔记都安全地保存在云端，卸载后随时重新安装、登录同一账号即可找回。",f_labelC,g_dim,cx-280,y,560,18);
    y+=18+6;
    Txt(L"也可以直接用网页版，不卸载也能继续用。",f_labelC,g_dim,cx-280,y,560,18);
    y+=18+30;
    float stayW=BtnW(L"再想想",f_btn,38);
    float goW=Measure(L"仍要卸载",f_label);
    float l0=cx-(stayW+28+goW)/2;
    rcRetainStay={(LONG)l0,(LONG)y,(LONG)(l0+stayW),(LONG)(y+44)};
    PrimaryBtn(l0,y,l0+stayW,y+44,L"再想想",rcRetainStay);
    float gx=l0+stayW+28;
    rcRetainGo={(LONG)gx,(LONG)y,(LONG)(gx+goW),(LONG)(y+30)};
    ID2D1Brush* gb=Hover(rcRetainGo)?(ID2D1Brush*)g_red:(ID2D1Brush*)g_text;
    Txt(L"仍要卸载",f_label,gb,gx,y+13,goW,18);
    g_rt->DrawLine(D2D1::Point2F(gx,y+30),D2D1::Point2F(gx+goW,y+30),gb,1.0f);
    y+=44+24;
    float webW=Measure(L"改用网页版 ↗",f_label)+48;
    float wl=cx-webW/2;
    rcRetainWeb={(LONG)wl,(LONG)y,(LONG)(wl+webW),(LONG)(y+40)};
    bool wh=Hover(rcRetainWeb);
    RRect(wl,y,wl+webW,y+40,20,wh?g_blueTintH:g_blueTint,1,g_border);
    Txt(L"改用网页版 ↗",f_label,g_blueGlow,wl,y+11,webW,20);
}

static void DrawTermsModal(){
    g_rt->FillRectangle(D2D1::RectF(0,0,W,H), g_overlay);
    float cx=430, ml=cx-260, mt=80, mr=cx+260, mb=520;
    RRect(ml,mt,mr,mb,18,g_modalBg,1,g_border);
    Txt(g_termsIsPrivacy?L"隐私协议":L"服务条款",f_termsTitle,g_white,ml+18,mt+14,300,20);
    float bx=mr-18-34, by=mt+14;
    rcTermsClose={(LONG)bx,(LONG)by,(LONG)(bx+34),(LONG)(by+26)};
    if(Hover(rcTermsClose)){ RRect(bx,by,bx+34,by+26,7,g_closeRed); Txt(L"✕",f_tb,g_white,bx,by+5,34,16); }
    else Txt(L"✕",f_tb,g_text,bx,by+5,34,16);
    const wchar_t* body=g_termsIsPrivacy?kPrivacy:kTerms;
    float bl=ml+22, bt=mt+44, br=mr-22, bb=mb-18;
    IDWriteTextLayout* tl=nullptr;
    g_dw->CreateTextLayout(body,(UINT32)wcslen(body),f_sub,br-bl,10000,&tl);
    tl->SetLineSpacing(DWRITE_LINE_SPACING_METHOD_UNIFORM, 28.0f, 28.0f);
    DWRITE_TEXT_METRICS m{}; tl->GetMetrics(&m);
    g_termsMaxScroll = m.height - (bb-bt); if(g_termsMaxScroll<0) g_termsMaxScroll=0;
    if(g_termsScroll>g_termsMaxScroll) g_termsScroll=g_termsMaxScroll;
    g_rt->PushAxisAlignedClip(D2D1::RectF(bl,bt,br,bb), D2D1_ANTIALIAS_MODE_ALIASED);
    g_rt->DrawTextLayout(D2D1::Point2F(bl, bt-g_termsScroll), tl, g_dim);
    g_rt->PopAxisAlignedClip();
    tl->Release();
    rcTermsPanel={(LONG)ml,(LONG)mt,(LONG)mr,(LONG)mb};
    rcTermsModal={0,0,W,H};
}

static void Render(){
    if(g_target){ g_target->Release(); g_target=nullptr; }
    IDXGISurface* surface=nullptr; g_swap->GetBuffer(0, __uuidof(IDXGISurface), (void**)&surface);
    D2D1_BITMAP_PROPERTIES1 bp = D2D1::BitmapProperties1(D2D1_BITMAP_OPTIONS_TARGET | D2D1_BITMAP_OPTIONS_CANNOT_DRAW, D2D1::PixelFormat(DXGI_FORMAT_B8G8R8A8_UNORM, D2D1_ALPHA_MODE_PREMULTIPLIED));
    g_rt->CreateBitmapFromDxgiSurface(surface, &bp, &g_target);
    surface->Release();
    g_rt->SetTarget(g_target);
    g_rt->BeginDraw();
    g_rt->Clear(D2D1::ColorF(0,0,0,0));
    g_rt->FillRectangle(D2D1::RectF(0,0,W,H),g_bg);
    g_rt->FillEllipse(D2D1::Ellipse(D2D1::Point2F(W-110,70),190,190),g_glow);
    for(auto& s:kStars){ g_white->SetColor(D2D1::ColorF(1,1,1,s.a)); g_rt->FillEllipse(D2D1::Ellipse(D2D1::Point2F(s.x*W,s.y*H),s.r,s.r),g_white); }
    g_white->SetColor(D2D1::ColorF(1,1,1));
    // 标题栏（44px 高）
    Txt(L"知屿",f_name,g_text,18,13,60,18);
    if(Hover(rcMin)) RRect((float)rcMin.left,(float)rcMin.top,(float)rcMin.right,(float)rcMin.bottom,7,g_titleHover);
    Txt(L"─",f_tb,g_text,(float)rcMin.left,(float)rcMin.top+5,(float)(rcMin.right-rcMin.left),16);
    if(Hover(rcClose)){ RRect((float)rcClose.left,(float)rcClose.top,(float)rcClose.right,(float)rcClose.bottom,7,g_closeRed); Txt(L"✕",f_tb,g_white,(float)rcClose.left,(float)rcClose.top+5,(float)(rcClose.right-rcClose.left),16); }
    else Txt(L"✕",f_tb,g_text,(float)rcClose.left,(float)rcClose.top+5,(float)(rcClose.right-rcClose.left),16);
    switch(g_page){
    case P_WELCOME: DrawWelcome(); break;
    case P_PREVIEW: DrawPreview(); break;
    case P_THEME: DrawTheme(); break;
    case P_CONFIG: DrawConfig(); break;
    case P_PROGRESS: DrawProgress(); break;
    case P_DONE: DrawDone(); break;
    case P_UNINSTALL: DrawUninstall(); break;
    case P_RETAIN: DrawRetain(); break;
    }
    if(g_showTerms) DrawTermsModal();
    HRESULT hrEnd=g_rt->EndDraw();
    static int diagCount=0;
    if(diagCount<3){ FILE* l=fopen("render_diag.txt", diagCount==0?"w":"a"); if(l){ fprintf(l,"EndDraw=0x%08X white=%p text=%p bg=%p page=%d\n",(unsigned)hrEnd,(void*)g_white,(void*)g_text,(void*)g_bg,(int)g_page); fclose(l);} diagCount++; }
    g_swap->Present(1, 0);
    g_dcomp->Commit();
}

static bool In(const RECT& r,POINT p){ return p.x>=r.left&&p.x<=r.right&&p.y>=r.top&&p.y<=r.bottom; }
static bool Hover(const RECT& r){ return g_mx>=r.left&&g_mx<=r.right&&g_my>=r.top&&g_my<=r.bottom; }
static void Invalidate(){ InvalidateRect(g_hwnd,nullptr,FALSE); }

// ── 安装/卸载逻辑 ──
static void SetProg(int pct,const wchar_t* msg){ g_pct=pct; g_progText=msg; Invalidate(); UpdateWindow(g_hwnd); }
static bool ExtractZipToTemp(std::wstring& outZip){
    HRSRC res=FindResourceW(GetModuleHandleW(nullptr),MAKEINTRESOURCEW(IDR_GREEN),RT_RCDATA); if(!res) return false;
    HGLOBAL h=LoadResource(GetModuleHandleW(nullptr),res); DWORD size=SizeofResource(GetModuleHandleW(nullptr),res); void* data=LockResource(h);
    wchar_t tmp[MAX_PATH]; GetTempPathW(MAX_PATH,tmp); outZip=std::wstring(tmp)+L"zhiyu-green.zip";
    HANDLE f=CreateFileW(outZip.c_str(),GENERIC_WRITE,0,nullptr,CREATE_ALWAYS,0,nullptr); if(f==INVALID_HANDLE_VALUE) return false;
    DWORD wr; WriteFile(f,data,size,&wr,nullptr); CloseHandle(f); return true;
}
static bool RunTar(const std::wstring& zip,const std::wstring& target){
    std::wstring cmd=L"tar.exe -xf \""+zip+L"\" -C \""+target+L"\"";
    STARTUPINFOW si={sizeof(si)}; PROCESS_INFORMATION pi={};
    std::vector<wchar_t> buf(cmd.begin(),cmd.end()); buf.push_back(0);
    bool ok=CreateProcessW(nullptr,buf.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW,nullptr,nullptr,&si,&pi);
    if(ok){ WaitForSingleObject(pi.hProcess,120000); CloseHandle(pi.hThread); CloseHandle(pi.hProcess); }
    return ok;
}
static void CreateShortcut(const std::wstring& targetDir){
    CoInitialize(nullptr); IShellLinkW* link=nullptr;
    if(SUCCEEDED(CoCreateInstance(CLSID_ShellLink,nullptr,CLSCTX_INPROC_SERVER,IID_IShellLinkW,(void**)&link))){
        std::wstring exe=targetDir+L"\\知屿.exe"; link->SetPath(exe.c_str()); link->SetWorkingDirectory(targetDir.c_str());
        IPersistFile* pf=nullptr; if(SUCCEEDED(link->QueryInterface(IID_IPersistFile,(void**)&pf))){
            wchar_t desktop[MAX_PATH]; SHGetFolderPathW(nullptr,CSIDL_DESKTOPDIRECTORY,nullptr,0,desktop);
            std::wstring lnk=std::wstring(desktop)+L"\\知屿.lnk"; pf->Save(lnk.c_str(),TRUE); pf->Release();
        }
        link->Release();
    }
    CoUninitialize();
}
static void SetRegStr(HKEY root,const wchar_t* sub,const wchar_t* name,const std::wstring& val){
    HKEY k; if(RegCreateKeyExW(root,sub,0,nullptr,0,KEY_WRITE,nullptr,&k,nullptr)==ERROR_SUCCESS){ RegSetValueExW(k,name,0,REG_SZ,(const BYTE*)val.c_str(),(DWORD)((val.size()+1)*sizeof(wchar_t))); RegCloseKey(k); }
}
static void DelRegKey(HKEY root,const wchar_t* sub){ RegDeleteTreeW(root,sub); }
static bool DoInstall(){
    CreateDirectoryW(g_dir.c_str(),nullptr);
    std::wstring zip; if(!ExtractZipToTemp(zip)){ g_lastError=L"安装资源缺失"; return false; }
    SetProg(8,L"正在解压安装文件…");
    if(!RunTar(zip,g_dir)){ g_lastError=L"解压失败"; return false; }
    DeleteFileW(zip.c_str());
    SetProg(72,L"写入主题配置…");
    wchar_t appdata[MAX_PATH]; SHGetFolderPathW(nullptr,CSIDL_APPDATA,nullptr,0,appdata);
    std::wstring confDir=std::wstring(appdata)+L"\\zhiyu"; CreateDirectoryW(confDir.c_str(),nullptr);
    std::wstring tn=g_theme==L"sky"?L"sky":g_theme==L"minimal"?L"minimal":L"starlight";
    std::wstring conf=L"{\"theme\":\""+tn+L"\"}";
    HANDLE cf=CreateFileW((confDir+L"\\config.json").c_str(),GENERIC_WRITE,0,nullptr,CREATE_ALWAYS,0,nullptr);
    if(cf!=INVALID_HANDLE_VALUE){ DWORD w; WriteFile(cf,conf.c_str(),(DWORD)(conf.size()*sizeof(wchar_t)),&w,nullptr); CloseHandle(cf); }
    if(g_shortcut){ SetProg(78,L"创建桌面快捷方式…"); CreateShortcut(g_dir); }
    if(g_autostart){ SetProg(84,L"设置开机自启动…"); SetRegStr(HKEY_CURRENT_USER,L"Software\\Microsoft\\Windows\\CurrentVersion\\Run",L"知屿",L"\""+g_dir+L"\\知屿.exe\""); }
    SetProg(90,L"创建卸载入口…");
    // 卸载器 = 本安装器自身（--uninstall 模式），硬链接/复制到安装目录
    wchar_t selfPath[MAX_PATH]; GetModuleFileNameW(nullptr,selfPath,MAX_PATH);
    std::wstring unExe=g_dir+L"\\知屿卸载.exe";
    if(GetFileAttributesW(unExe.c_str())==INVALID_FILE_ATTRIBUTES)
        if(!CreateHardLinkW(unExe.c_str(),selfPath,nullptr)) CopyFileW(selfPath,unExe.c_str(),FALSE);
    SetProg(95,L"写入注册表…");
    SetRegStr(HKEY_CURRENT_USER,L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\知屿",L"DisplayName",L"知屿");
    SetRegStr(HKEY_CURRENT_USER,L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\知屿",L"DisplayVersion",L"1.11.0");
    SetRegStr(HKEY_CURRENT_USER,L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\知屿",L"Publisher",L"知屿");
    SetRegStr(HKEY_CURRENT_USER,L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\知屿",L"InstallLocation",g_dir);
    SetRegStr(HKEY_CURRENT_USER,L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\知屿",L"UninstallString",L"\""+g_dir+L"\\知屿卸载.exe\" --uninstall");
    SetProg(100,L"安装完成"); return true;
}
static void DeleteDirRecursive(const std::wstring& dir){
    std::wstring pat=dir+L"\\*";
    WIN32_FIND_DATAW fd; HANDLE h=FindFirstFileW(pat.c_str(),&fd);
    if(h==INVALID_HANDLE_VALUE) return;
    do{
        if(wcscmp(fd.cFileName,L".")==0||wcscmp(fd.cFileName,L"..")==0) continue;
        std::wstring full=dir+L"\\"+fd.cFileName;
        if(fd.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY) DeleteDirRecursive(full);
        else{ SetFileAttributesW(full.c_str(),FILE_ATTRIBUTE_NORMAL); DeleteFileW(full.c_str()); }
    }while(FindNextFileW(h,&fd));
    FindClose(h);
    SetFileAttributesW(dir.c_str(),FILE_ATTRIBUTE_NORMAL);
    RemoveDirectoryW(dir.c_str());
}
static void DoUninstall(){
    SetProg(5,L"正在结束知屿进程…");
    _wsystem(L"taskkill /f /im 知屿.exe >nul 2>&1"); Sleep(700);
    SetProg(30,L"正在删除桌面快捷方式…");
    wchar_t desktop[MAX_PATH]; SHGetFolderPathW(nullptr,CSIDL_DESKTOPDIRECTORY,nullptr,0,desktop);
    DeleteFileW((std::wstring(desktop)+L"\\知屿.lnk").c_str());
    wchar_t pub[MAX_PATH]; SHGetFolderPathW(nullptr,CSIDL_COMMON_DESKTOPDIRECTORY,nullptr,0,pub);
    DeleteFileW((std::wstring(pub)+L"\\知屿.lnk").c_str());
    SetProg(50,L"正在清理注册表…");
    DelRegKey(HKEY_CURRENT_USER,L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\知屿");
    HKEY run; if(RegOpenKeyExW(HKEY_CURRENT_USER,L"Software\\Microsoft\\Windows\\CurrentVersion\\Run",0,KEY_SET_VALUE,&run)==ERROR_SUCCESS){ RegDeleteValueW(run,L"知屿"); RegCloseKey(run); }
    if(g_purge){
        SetProg(65,L"正在清理本地个人数据…");
        wchar_t appdata[MAX_PATH]; SHGetFolderPathW(nullptr,CSIDL_APPDATA,nullptr,0,appdata);
        DeleteDirRecursive(std::wstring(appdata)+L"\\zhiyu"); DeleteDirRecursive(std::wstring(appdata)+L"\\知屿");
    }
    SetProg(80,L"正在删除程序文件…");
    for(int i=0;i<6;i++){
        DeleteDirRecursive(g_dir);
        if(GetFileAttributesW(g_dir.c_str())==INVALID_FILE_ATTRIBUTES) break;
        Sleep(400);
    }
    SetProg(100,L"卸载完成");
}

static void OnClick(POINT p){
    if(g_showTerms){ if(In(rcTermsClose,p)||!In(rcTermsPanel,p)) g_showTerms=false; Invalidate(); return; }
    if(In(rcClose,p)){ DestroyWindow(g_hwnd); return; }
    if(In(rcMin,p)){ ShowWindow(g_hwnd,SW_MINIMIZE); return; }
    switch(g_page){
    case P_WELCOME:
        if(In(rcStart,p)) g_page=P_PREVIEW;
        else if(g_installed&&In(rcUninstall,p)){ g_uninstallDirText=L"将删除 "+g_dir+L" 下的程序、桌面快捷方式与开机自启项。"; g_page=P_UNINSTALL; }
        break;
    case P_PREVIEW:
        if(In(rcPvBack,p)) g_page=P_WELCOME;
        else if(In(rcPvNext,p)) g_page=P_THEME;
        break;
    case P_THEME:
        if(In(rcThBack,p)) g_page=P_PREVIEW;
        else if(In(rcThNext,p)) g_page=P_CONFIG;
        else for(int i=0;i<3;i++) if(In(rcThemeRows[i],p)){ g_theme=g_selTheme=(i==0?L"starlight":i==1?L"sky":L"minimal"); break; }
        break;
    case P_CONFIG:
        if(In(rcConfigBack,p)) g_page=P_THEME;
        else if(In(rcBrowse,p)){
            BROWSEINFOW bi={}; bi.hwndOwner=g_hwnd; bi.lpszTitle=L"选择安装位置"; bi.ulFlags=BIF_RETURNONLYFSDIRS|BIF_NEWDIALOGSTYLE;
            PIDLIST_ABSOLUTE pidl=SHBrowseForFolderW(&bi);
            if(pidl){ wchar_t path[MAX_PATH]; if(SHGetPathFromIDListW(pidl,path)){ std::wstring clean=path; while(!clean.empty()&&clean.back()=='\\') clean.pop_back(); g_dir=clean+L"\\知屿"; } CoTaskMemFree(pidl); }
        }
        else if(In(rcChkShortcut,p)) g_shortcut=!g_shortcut;
        else if(In(rcChkAutoStart,p)) g_autostart=!g_autostart;
        else if(In(rcChkAgree,p)) g_agree=!g_agree;
        else if(In(rcLinkTerms,p)){ g_termsIsPrivacy=false; g_showTerms=true; }
        else if(In(rcLinkPrivacy,p)){ g_termsIsPrivacy=true; g_showTerms=true; }
        else if(In(rcInstall,p)){
            if(g_dir.empty()) break;
            if(!g_agree){ MessageBoxW(g_hwnd,L"请先阅读并同意服务条款与隐私协议。",L"知屿",MB_OK); break; }
            g_page=P_PROGRESS; g_pct=0; Invalidate(); UpdateWindow(g_hwnd);
            bool ok=DoInstall();
            g_doneText=ok?L"":L"失败："+g_lastError;
            g_page=ok?P_DONE:P_CONFIG;
        }
        break;
    case P_DONE:
        if(In(rcDone,p)) DestroyWindow(g_hwnd);
        else if(In(rcLaunch,p)){ ShellExecuteW(nullptr,L"open",(g_dir+L"\\知屿.exe").c_str(),nullptr,g_dir.c_str(),SW_SHOW); DestroyWindow(g_hwnd); }
        break;
    case P_UNINSTALL:
        if(In(rcUnCancel,p)) g_page=P_WELCOME;
        else if(In(rcChkPurge,p)) g_purge=!g_purge;
        else if(In(rcUnGo,p)) g_page=P_RETAIN;
        break;
    case P_RETAIN:
        if(In(rcRetainStay,p)) DestroyWindow(g_hwnd);
        else if(In(rcRetainWeb,p)) ShellExecuteW(nullptr,L"open",L"http://182.254.209.123/zhiyu/",nullptr,nullptr,SW_SHOW);
        else if(In(rcRetainGo,p)){ g_uninstalling=true; g_page=P_PROGRESS; g_pct=0; Invalidate(); UpdateWindow(g_hwnd); DoUninstall(); g_doneText=L"知屿 已从你的电脑移除，云端笔记数据仍然保留。"; g_page=P_DONE; Invalidate(); }
        break;
    default: break;
    }
    Invalidate();
}

static POINT Logical(LPARAM l){ POINT p={GET_X_LPARAM(l),GET_Y_LPARAM(l)}; p.x=(LONG)(p.x/g_scale); p.y=(LONG)(p.y/g_scale); return p; }

static LRESULT CALLBACK WndProc(HWND hwnd,UINT msg,WPARAM w,LPARAM l){
    switch(msg){
    case WM_CREATE:
        rcMin={W-80,9,W-46,35}; rcClose={W-46,9,W-12,35};
        EnableAcrylic(hwnd); InitD2D(hwnd);
        return 0;
    case WM_LBUTTONDOWN:{ POINT p=Logical(l); OnClick(p); return 0; }
    case WM_NCHITTEST:{ POINT p={GET_X_LPARAM(l),GET_Y_LPARAM(l)}; ScreenToClient(hwnd,&p); float px=p.x/g_scale, py=p.y/g_scale; if(py<=44&&px<780) return HTCAPTION; break; }
    case WM_MOUSEMOVE: {
        POINT p=Logical(l); g_mx=p.x; g_my=p.y;
        TRACKMOUSEEVENT tme={sizeof(tme),TME_LEAVE,hwnd,0};
        TrackMouseEvent(&tme);
        Invalidate();
        return 0;
    }
    case WM_MOUSELEAVE: g_mx=-1; g_my=-1; Invalidate(); return 0;
    case WM_MOUSEWHEEL: {
        if(g_showTerms){
            g_termsScroll -= (GET_WHEEL_DELTA_WPARAM(w)/120.0f)*60.0f;
            if(g_termsScroll<0) g_termsScroll=0;
            if(g_termsScroll>g_termsMaxScroll) g_termsScroll=g_termsMaxScroll;
            Invalidate(); return 0;
        }
        break;
    }
    case WM_PAINT:{ PAINTSTRUCT ps; BeginPaint(hwnd,&ps); EndPaint(hwnd,&ps); Render(); return 0; }
    case WM_ERASEBKGND: return 1;
    case WM_DESTROY: PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(hwnd,msg,w,l);
}

static void LoadState(){
    wchar_t local[MAX_PATH]; SHGetFolderPathW(nullptr,CSIDL_LOCAL_APPDATA,nullptr,0,local);
    g_dir=std::wstring(local)+L"\\知屿";
    HKEY k; if(RegOpenKeyExW(HKEY_CURRENT_USER,L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\知屿",0,KEY_READ,&k)==ERROR_SUCCESS){
        wchar_t v[1024]; DWORD sz=sizeof(v);
        if(RegQueryValueExW(k,L"InstallLocation",nullptr,nullptr,(LPBYTE)v,&sz)==ERROR_SUCCESS){
            std::wstring root=v; if(GetFileAttributesW(root.c_str())!=INVALID_FILE_ATTRIBUTES){ g_dir=root; g_installed=true; }
        }
        RegCloseKey(k);
    }
}

int WINAPI wWinMain(HINSTANCE hInst,HINSTANCE,PWSTR,int){
    SetProcessDPIAware();
    HDC sdc=GetDC(nullptr); int dpi=GetDeviceCaps(sdc,LOGPIXELSX); ReleaseDC(nullptr,sdc);
    g_scale = dpi / 96.0f;
    WNDCLASSW wc={}; wc.lpfnWndProc=WndProc; wc.hInstance=hInst; wc.lpszClassName=L"ZhiyuInstallerCpp3"; wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);
    RegisterClassW(&wc);
    LoadState();
    // 卸载器模式：exe 文件名含"卸载" 或带 --uninstall → 直接进卸载页（点击即卸载，无需重开安装器）
    {
        wchar_t selfPath[MAX_PATH]; GetModuleFileNameW(nullptr,selfPath,MAX_PATH);
        std::wstring sp=selfPath; size_t slash=sp.find_last_of(L"\\/");
        std::wstring selfName=(slash==std::wstring::npos)?sp:sp.substr(slash+1);
        bool uninst = selfName.find(L"卸载")!=std::wstring::npos;
        int n=0; LPWSTR* av=CommandLineToArgvW(GetCommandLineW(),&n);
        for(int i=1;i<n;i++) if(wcscmp(av[i],L"--uninstall")==0) uninst=true;
        if(av) LocalFree(av);
        if(uninst){
            if(slash!=std::wstring::npos) g_dir=sp.substr(0,slash);
            g_uninstallDirText=L"将删除 "+g_dir+L" 下的程序、桌面快捷方式与开机自启项。";
            g_page=P_UNINSTALL;
        }
    }
    g_hwnd=CreateWindowExW(0,wc.lpszClassName,L"知屿安装",WS_POPUP|WS_MINIMIZEBOX,
        (GetSystemMetrics(SM_CXSCREEN)-(int)(W*g_scale))/2,(GetSystemMetrics(SM_CYSCREEN)-(int)(H*g_scale))/2,
        (int)(W*g_scale),(int)(H*g_scale),nullptr,nullptr,hInst,nullptr);
    ShowWindow(g_hwnd,SW_SHOW); UpdateWindow(g_hwnd);
    MSG m; while(GetMessageW(&m,nullptr,0,0)>0){ TranslateMessage(&m); DispatchMessageW(&m); }
    return 0;
}
