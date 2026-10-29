// Agentic-Z desktop — Tauri entry point (D2).
//
// D2 changes vs D1:
//   - Adds tauri-plugin-notification for native Windows toasts on log_error events.
//   - Drops tauri-plugin-fs (frontend doesn't need direct fs access; sidecar
//     handles it all over HTTP).
//
// Responsibilities:
//   - Spawn the Python FastAPI sidecar at startup.
//   - Wait for the sidecar's port file at .claude/local-memory/agentic-z-desktop.port.
//   - Expose `get_sidecar_status` and `get_repo_root` Tauri commands.
//   - Clean shutdown: kill the sidecar on window close.

#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use serde::Serialize;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

#[derive(Serialize, Default, Clone)]
struct SidecarStatus {
    port: Option<u16>,
    pid: Option<u32>,
    error: Option<String>,
}

struct AppState {
    child: Mutex<Option<Child>>,
    status: Mutex<SidecarStatus>,
}

fn resolve_sidecar_main(app_handle: &tauri::AppHandle) -> Result<PathBuf, String> {
    if cfg!(debug_assertions) {
        let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
        let candidate = cwd.join("..").join("sidecar").join("main.py");
        if candidate.exists() {
            return Ok(candidate);
        }
        return Err(format!(
            "Dev sidecar not found at {:?}. Run from desktop/ folder.",
            candidate
        ));
    }
    app_handle
        .path()
        .resource_dir()
        .map_err(|e| e.to_string())
        .and_then(|d| {
            let p = d.join("sidecar").join("main.py");
            if p.exists() {
                Ok(p)
            } else {
                Err(format!("Bundled sidecar not found at {:?}", p))
            }
        })
}

fn read_port_file(repo_root: &PathBuf) -> Option<u16> {
    let port_file = repo_root
        .join(".claude")
        .join("local-memory")
        .join("agentic-z-desktop.port");
    let raw = std::fs::read_to_string(&port_file).ok()?;
    let parsed: serde_json::Value = serde_json::from_str(&raw).ok()?;
    parsed.get("port")?.as_u64().map(|n| n as u16)
}

fn spawn_sidecar(app_handle: &tauri::AppHandle, repo_root: &PathBuf) -> Result<Child, String> {
    let main_py = resolve_sidecar_main(app_handle)?;
    let python = if cfg!(target_os = "windows") {
        "python"
    } else {
        "python3"
    };
    Command::new(python)
        .arg(&main_py)
        .current_dir(repo_root)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to spawn sidecar: {}", e))
}

#[tauri::command]
fn get_sidecar_status(state: tauri::State<'_, AppState>) -> SidecarStatus {
    state.status.lock().unwrap().clone()
}

#[tauri::command]
fn get_repo_root() -> Result<String, String> {
    let mut cur = std::env::current_dir().map_err(|e| e.to_string())?;
    for _ in 0..10 {
        if cur.join("CLAUDE.md").exists() {
            return Ok(cur.to_string_lossy().to_string());
        }
        if !cur.pop() {
            break;
        }
    }
    Err("repo root not found (CLAUDE.md missing in any parent directory)".to_string())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .manage(AppState {
            child: Mutex::new(None),
            status: Mutex::new(SidecarStatus::default()),
        })
        .invoke_handler(tauri::generate_handler![
            get_sidecar_status,
            get_repo_root
        ])
        .setup(|app| {
            let app_handle = app.handle().clone();
            let state = app.state::<AppState>();

            let mut cur = std::env::current_dir().expect("cwd available");
            let mut repo_root: Option<PathBuf> = None;
            for _ in 0..10 {
                if cur.join("CLAUDE.md").exists() {
                    repo_root = Some(cur.clone());
                    break;
                }
                if !cur.pop() {
                    break;
                }
            }
            let repo_root = match repo_root {
                Some(p) => p,
                None => {
                    let mut s = state.status.lock().unwrap();
                    s.error = Some("repo root not found".into());
                    return Ok(());
                }
            };

            match spawn_sidecar(&app_handle, &repo_root) {
                Ok(child) => {
                    let pid = child.id();
                    *state.child.lock().unwrap() = Some(child);
                    let mut s = state.status.lock().unwrap();
                    s.pid = Some(pid);
                }
                Err(e) => {
                    let mut s = state.status.lock().unwrap();
                    s.error = Some(e);
                    return Ok(());
                }
            };

            let app_handle_for_thread = app.handle().clone();
            let repo_root_clone = repo_root.clone();
            std::thread::spawn(move || {
                for _ in 0..50 {
                    std::thread::sleep(Duration::from_millis(200));
                    if let Some(port) = read_port_file(&repo_root_clone) {
                        let s = app_handle_for_thread.state::<AppState>();
                        let mut status = s.status.lock().unwrap();
                        status.port = Some(port);
                        return;
                    }
                }
                let s = app_handle_for_thread.state::<AppState>();
                let mut status = s.status.lock().unwrap();
                status.error = Some("sidecar started but port file never appeared".into());
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let state: tauri::State<'_, AppState> = window.state();
                let child_opt = state.child.lock().unwrap().take();
                if let Some(mut child) = child_opt {
                    let _ = child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Agentic-Z");
}
