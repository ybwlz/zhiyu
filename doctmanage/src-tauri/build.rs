fn main() {
    tauri_build::try_build(
        tauri_build::Attributes::new().app_manifest(
            tauri_build::AppManifest::new().commands(&[
                "app_version",
                "set_title_bar_color",
                "set_auto_launch",
                "get_auto_launch",
                "quit_app",
                "is_uninstall_mode",
                "uninstall_app",
                "check_update",
            ]),
        ),
    )
    .expect("failed to run tauri-build");
}
