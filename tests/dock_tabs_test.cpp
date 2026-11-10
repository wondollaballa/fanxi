/* Regression test for the HUD tab-group behaviour added to the vendored Dear ImGui:
 *
 *   - a floating tab group grows to the selected window's own size when a tab is selected;
 *   - a manual resize survives until the next tab selection;
 *   - the tab bar's window-menu button minimizes the whole group to its tab bar and restores
 *     the size it had before;
 *   - selecting a tab while the group is minimized opens it back up at that tab's size.
 *
 * Build and run (needs build/third_party/imgui.a from tools/thirdparty.py; no game files):
 *
 *   clang++ -std=c++17 -O1 -Ithird_party/imgui \
 *     '-DIMGUI_USER_CONFIG="../../host/addons/imconfig_xi.h"' \
 *     tests/dock_tabs_test.cpp build/third_party/imgui.a -o build/dock_tabs_test
 *   build/dock_tabs_test
 */
#include "imgui.h"
#include "imgui_internal.h"

#include <stdint.h>
#include <stdio.h>

static int g_failed;

// Declared by host/addons/imconfig_xi.h, which the vendored ImGui archive is built with.
extern "C" void xi_imgui_assert(const char* expr, const char* file, int line)
{
    printf("imgui assert: %s (%s:%d)\n", expr, file, line);
    ++g_failed;
}

static void check(bool condition, const char* label, const char* detail = "")
{
    if (condition)
    {
        printf("ok %s\n", label);
        return;
    }
    ++g_failed;
    printf("FAIL %s %s\n", label, detail);
}

static void finish_render()
{
    ImGui::Render();
    // A renderer backend that accepts the font atlas requests: the headless test has no GPU.
    ImDrawData* dd = ImGui::GetDrawData();
    if (dd && dd->Textures)
        for (ImTextureData* td : *dd->Textures)
        {
            if (td->Status == ImTextureStatus_WantCreate)
                td->SetTexID((ImTextureID)(uintptr_t)td->UniqueID + 1), td->SetStatus(ImTextureStatus_OK);
            else if (td->Status == ImTextureStatus_WantUpdates)
                td->SetStatus(ImTextureStatus_OK);
            else if (td->Status == ImTextureStatus_WantDestroy)
                td->SetTexID(ImTextureID_Invalid), td->SetStatus(ImTextureStatus_Destroyed);
        }
}

static void frame()
{
    ImGuiIO& io = ImGui::GetIO();
    io.DisplaySize = ImVec2(1280, 720);
    io.DeltaTime = 1.0f / 60.0f;
    ImGui::NewFrame();

    // The two tabs request very different sizes, so the group's size names the tab it fitted.
    ImGui::SetNextWindowDockID(0x100, ImGuiCond_Always);
    ImGui::SetNextWindowSize(ImVec2(320, 220), ImGuiCond_Always);
    ImGui::Begin("WindowA", NULL, 0);
    ImGui::Text("A");
    ImGui::End();

    ImGui::SetNextWindowDockID(0x100, ImGuiCond_Always);
    ImGui::SetNextWindowSize(ImVec2(520, 420), ImGuiCond_Always);
    ImGui::Begin("WindowB", NULL, 0);
    ImGui::Text("B");
    ImGui::End();

    finish_render();
}

static void run(int frames)
{
    for (int i = 0; i < frames; ++i)
        frame();
}

static ImGuiDockNode* node()
{
    return ImGui::DockContextFindNodeByID(ImGui::GetCurrentContext(), 0x100);
}

static void focus_window(const char* name)
{
    ImGui::FocusWindow(ImGui::FindWindowByName(name));
}

static void click_at(float x, float y)
{
    ImGuiIO& io = ImGui::GetIO();
    io.AddMousePosEvent(x, y);
    io.AddMouseButtonEvent(0, true);
    run(1);
    io.AddMouseButtonEvent(0, false);
    run(4);
}

static void check_size(ImGuiDockNode* dock, float w, float h, const char* label)
{
    char detail[160];
    snprintf(detail, sizeof detail, "(got %.0fx%.0f, want %.0fx%.0f)", dock->Size.x, dock->Size.y, w, h);
    check(dock->Size.x == w && dock->Size.y == h, label, detail);
}

int main()
{
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.BackendFlags |= ImGuiBackendFlags_RendererHasTextures;
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;
    io.IniFilename = NULL;
    ImGui::StyleColorsDark();

    run(6);
    ImGuiDockNode* dock = node();
    if (!dock)
    {
        printf("FAIL no dock node\n");
        ImGui::DestroyContext();
        return 1;
    }

    ImGuiWindow* a = ImGui::FindWindowByName("WindowA");
    ImGuiWindow* b = ImGui::FindWindowByName("WindowB");
    check(a && b, "both windows are docked");
    check(a && a->DockRequestedSize.x == 320.0f && a->DockRequestedSize.y == 220.0f,
          "window A's own size is captured", "");
    check(b && b->DockRequestedSize.x == 520.0f && b->DockRequestedSize.y == 420.0f,
          "window B's own size is captured", "");
    check(dock->VisibleWindow == b, "the last docked tab is selected");
    check_size(dock, 520, 420, "the group fits the selected tab");

    // A manual resize is the user's until they pick another tab.
    dock->Size = ImVec2(400, 300);
    dock->HostWindow->Size = dock->HostWindow->SizeFull = dock->Size;
    run(3);
    check_size(dock, 400, 300, "a manual resize is kept while the tab stays selected");

    focus_window("WindowA");
    run(3);
    check_size(dock, 320, 220, "selecting tab A fits the group to A");

    focus_window("WindowB");
    run(3);
    check_size(dock, 520, 420, "selecting tab B fits the group to B");

    // The minimize button sits at the left of the tab bar. Click above the bottom resize
    // border: the group is only a tab bar tall.
    const float button_x = dock->Pos.x + 12.0f;
    const float button_y = dock->Pos.y + 6.0f;
    click_at(button_x, button_y);
    check(dock->IsMinimized, "the tab-bar button minimizes the group");
    check(dock->RestoreSize.x == 520.0f && dock->RestoreSize.y == 420.0f,
          "the group remembers its expanded size", "");
    check(dock->Size.y == ImGui::GetFrameHeight(), "a minimized group is its tab bar",
          "");

    focus_window("WindowA");
    run(3);
    check(!dock->IsMinimized, "selecting a tab opens a minimized group");
    check_size(dock, 320, 220, "the reopened group fits the selected tab");

    click_at(button_x, button_y);
    check(dock->IsMinimized, "the group minimizes again");
    click_at(button_x, button_y);
    check(!dock->IsMinimized, "clicking the button again maximizes the group");
    check_size(dock, 320, 220, "maximizing restores the size the group had");

    // A tab dragged out of a minimized group must not keep the tab-bar height as its floating
    // size: the action windows cannot be resized by hand.
    click_at(button_x, button_y);
    check(dock->IsMinimized, "the group minimizes before undocking a tab");
    ImGui::DockContextProcessUndockWindow(ImGui::GetCurrentContext(), b, false);
    check(b->SizeFull.x == 320.0f && b->SizeFull.y == 220.0f,
          "an undocked tab gets the group's expanded size, not the tab-bar height");

    ImGui::DestroyContext();
    if (g_failed)
    {
        printf("dock_tabs_test: %d failure(s)\n", g_failed);
        return 1;
    }
    printf("dock_tabs_test: PASS\n");
    return 0;
}
