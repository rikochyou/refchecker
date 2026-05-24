#include "flutter_window.h"

#include <commdlg.h>
#include <flutter/encodable_value.h>
#include <flutter/method_channel.h>
#include <flutter/standard_method_codec.h>
#include <shlobj.h>
#include <windows.h>

#include <optional>
#include <string>

#include "flutter/generated_plugin_registrant.h"

namespace {

std::string WideToUtf8(const std::wstring& value) {
  if (value.empty()) {
    return "";
  }
  int size_needed = WideCharToMultiByte(CP_UTF8, 0, value.c_str(),
                                        static_cast<int>(value.size()), nullptr,
                                        0, nullptr, nullptr);
  std::string result(size_needed, 0);
  WideCharToMultiByte(CP_UTF8, 0, value.c_str(), static_cast<int>(value.size()),
                      result.data(), size_needed, nullptr, nullptr);
  return result;
}

std::wstring Utf8ToWide(const std::string& value) {
  if (value.empty()) {
    return L"";
  }
  int size_needed = MultiByteToWideChar(CP_UTF8, 0, value.c_str(),
                                        static_cast<int>(value.size()), nullptr,
                                        0);
  std::wstring result(size_needed, 0);
  MultiByteToWideChar(CP_UTF8, 0, value.c_str(), static_cast<int>(value.size()),
                      result.data(), size_needed);
  return result;
}

std::optional<std::string> PickReferenceFile(HWND owner) {
  wchar_t file_name[MAX_PATH] = {0};
  OPENFILENAMEW dialog = {0};
  dialog.lStructSize = sizeof(dialog);
  dialog.hwndOwner = owner;
  dialog.lpstrFilter =
      L"Reference files (*.bib;*.docx)\0*.bib;*.docx\0"
      L"BibTeX files (*.bib)\0*.bib\0"
      L"Word documents (*.docx)\0*.docx\0"
      L"All files (*.*)\0*.*\0";
  dialog.lpstrFile = file_name;
  dialog.nMaxFile = MAX_PATH;
  dialog.lpstrTitle = L"Select BibTeX or DOCX reference file";
  dialog.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR;

  if (GetOpenFileNameW(&dialog) == TRUE) {
    return WideToUtf8(file_name);
  }
  return std::nullopt;
}

int CALLBACK BrowseCallbackProc(HWND hwnd, UINT message, LPARAM, LPARAM data) {
  if (message == BFFM_INITIALIZED && data != 0) {
    SendMessage(hwnd, BFFM_SETSELECTION, TRUE, data);
  }
  return 0;
}

std::optional<std::string> PickOutputDir(HWND owner,
                                         const flutter::EncodableValue* args) {
  std::wstring initial_directory;
  if (args && std::holds_alternative<flutter::EncodableMap>(*args)) {
    const auto& map = std::get<flutter::EncodableMap>(*args);
    auto it = map.find(flutter::EncodableValue("initialDirectory"));
    if (it != map.end() && std::holds_alternative<std::string>(it->second)) {
      initial_directory = Utf8ToWide(std::get<std::string>(it->second));
    }
  }

  BROWSEINFOW browse = {0};
  browse.hwndOwner = owner;
  browse.lpszTitle = L"Select output folder";
  browse.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE;
  browse.lpfn = initial_directory.empty() ? nullptr : BrowseCallbackProc;
  browse.lParam = initial_directory.empty()
                      ? 0
                      : reinterpret_cast<LPARAM>(initial_directory.c_str());

  PIDLIST_ABSOLUTE item_id_list = SHBrowseForFolderW(&browse);
  if (!item_id_list) {
    return std::nullopt;
  }

  wchar_t path[MAX_PATH] = {0};
  bool ok = SHGetPathFromIDListW(item_id_list, path) == TRUE;
  CoTaskMemFree(item_id_list);
  if (ok) {
    return WideToUtf8(path);
  }
  return std::nullopt;
}

}  // namespace

FlutterWindow::FlutterWindow(const flutter::DartProject& project)
    : project_(project) {}

FlutterWindow::~FlutterWindow() {}

bool FlutterWindow::OnCreate() {
  if (!Win32Window::OnCreate()) {
    return false;
  }

  RECT frame = GetClientArea();

  // The size here must match the window dimensions to avoid unnecessary surface
  // creation / destruction in the startup path.
  flutter_controller_ = std::make_unique<flutter::FlutterViewController>(
      frame.right - frame.left, frame.bottom - frame.top, project_);
  // Ensure that basic setup of the controller was successful.
  if (!flutter_controller_->engine() || !flutter_controller_->view()) {
    return false;
  }
  RegisterPlugins(flutter_controller_->engine());

  auto channel =
      std::make_unique<flutter::MethodChannel<flutter::EncodableValue>>(
          flutter_controller_->engine()->messenger(),
          "refchecker/native_dialogs",
          &flutter::StandardMethodCodec::GetInstance());

  channel->SetMethodCallHandler(
      [this](const flutter::MethodCall<flutter::EncodableValue>& call,
             std::unique_ptr<flutter::MethodResult<flutter::EncodableValue>>
                 result) {
        std::optional<std::string> selected;
        if (call.method_name() == "pickBibFile") {
          selected = PickReferenceFile(GetHandle());
        } else if (call.method_name() == "pickOutputDir") {
          selected = PickOutputDir(GetHandle(), call.arguments());
        } else {
          result->NotImplemented();
          return;
        }

        if (selected.has_value()) {
          result->Success(flutter::EncodableValue(selected.value()));
        } else {
          result->Success(flutter::EncodableValue());
        }
      });
  native_dialog_channel_ = std::move(channel);

  SetChildContent(flutter_controller_->view()->GetNativeWindow());

  flutter_controller_->engine()->SetNextFrameCallback([&]() {
    this->Show();
  });

  // Flutter can complete the first frame before the "show window" callback is
  // registered. The following call ensures a frame is pending to ensure the
  // window is shown. It is a no-op if the first frame hasn't completed yet.
  flutter_controller_->ForceRedraw();

  return true;
}

void FlutterWindow::OnDestroy() {
  if (flutter_controller_) {
    flutter_controller_ = nullptr;
  }

  Win32Window::OnDestroy();
}

LRESULT
FlutterWindow::MessageHandler(HWND hwnd, UINT const message,
                              WPARAM const wparam,
                              LPARAM const lparam) noexcept {
  // Give Flutter, including plugins, an opportunity to handle window messages.
  if (flutter_controller_) {
    std::optional<LRESULT> result =
        flutter_controller_->HandleTopLevelWindowProc(hwnd, message, wparam,
                                                      lparam);
    if (result) {
      return *result;
    }
  }

  switch (message) {
    case WM_FONTCHANGE:
      flutter_controller_->engine()->ReloadSystemFonts();
      break;
  }

  return Win32Window::MessageHandler(hwnd, message, wparam, lparam);
}
