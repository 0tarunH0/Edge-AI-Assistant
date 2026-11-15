#Requires AutoHotkey v2.0
#SingleInstance Force

^+x:: {
    ; 1. Release Shift so Send "^c" does not trigger Ctrl+Shift+C (DevTools/Terminal)
    KeyWait "Shift", "T0.3"
    SavedClip := ClipboardAll()
    A_Clipboard := ""
    Send "{Shift Up}^c"

    SelectedText := ""
    if ClipWait(0.6) {
        SelectedText := A_Clipboard
    }
    A_Clipboard := SavedClip

    ; 2. Default to Workflow 1 (Inline Text) if text is highlighted, else Workflow 4 (OS)
    HasSelection := (Trim(SelectedText) != "")
    DefaultWf := HasSelection ? "Choose1" : "Choose4"

    ; 3. Build launcher GUI with visible Highlighted Text + Instruction fields
    Launcher := Gui("+AlwaysOnTop -MinimizeBox", "Edge AI Assistant (llama3.1:8b)")
    Launcher.BackColor := "1E1E2E"
    Launcher.SetFont("s10 cCDD6F4", "Segoe UI")

    Launcher.AddText("xm ym", "Workflow:")
    WfDrop := Launcher.AddDropDownList("x+10 yp-3 w260 " . DefaultWf, [
        "1. Inline Text Formatting",
        "2. IDE Code Assistance",
        "3. Web-Augmented Q&A",
        "4. OS Task Automation (PowerShell)"
    ])

    Launcher.AddText("xm y+12", "Highlighted Selection (auto-captured):")
    ContextBox := Launcher.AddEdit("xm y+4 w380 r3 Background313244 cA6ADC8", SelectedText)

    Launcher.AddText("xm y+10", "Instruction / Prompt (leave blank to run selection directly):")
    PromptBox := Launcher.AddEdit("xm y+4 w380 r2 Background313244 cCDD6F4")

    RunBtn := Launcher.AddButton("xm y+12 w185 Default", "Run (Enter)")
    CancelBtn := Launcher.AddButton("x+10 yp w185", "Cancel (Esc)")

    RunBtn.OnEvent("Click", (*) => SubmitRequest(Launcher, WfDrop.Value, PromptBox.Value, ContextBox.Value))
    CancelBtn.OnEvent("Click", (*) => Launcher.Destroy())
    Launcher.OnEvent("Escape", (*) => Launcher.Destroy())

    Launcher.Show()
    PromptBox.Focus()
}

SubmitRequest(Launcher, WfIndex, PromptText, ContextText) {
    CleanPrompt := Trim(PromptText)
    CleanContext := Trim(ContextText)

    if (CleanPrompt = "" && CleanContext = "") {
        MsgBox("Please enter an instruction or highlight text first.", "Edge AI Assistant", "Icon!")
        return
    }

    ; If instruction is blank, treat the highlighted selection itself as the prompt
    if (CleanPrompt = "") {
        CleanPrompt := CleanContext
        CleanContext := ""
    }

    Launcher.Destroy()

    WorkflowMap := ["inline_text", "ide_code", "web_qa", "os_powershell"]
    WorkflowKey := WorkflowMap[WfIndex]

    Payload := '{'
        . '"workflow":"' . EscapeJson(WorkflowKey) . '",'
        . '"prompt":"' . EscapeJson(CleanPrompt) . '",'
        . '"selected_text":"' . EscapeJson(CleanContext) . '"'
        . '}'

    try {
        Http := ComObject("WinHttp.WinHttpRequest.5.1")
        Http.SetTimeouts(5000, 5000, 10000, 90000)
        Http.Open("POST", "http://127.0.0.1:8000/invoke", false)
        Http.SetRequestHeader("Content-Type", "application/json")
        Http.Send(Payload)

        if (Http.Status != 200) {
            MsgBox("Backend Error (" . Http.Status . "):`n" . Http.ResponseText, "Edge AI Assistant", "Iconx")
            return
        }

        OutputText := ExtractJsonField(Http.ResponseText, "output")

        if (WorkflowKey = "inline_text" || WorkflowKey = "ide_code") {
            A_Clipboard := OutputText
            Sleep 80
            Send "^v"
        } else {
            ShowResultWindow(WorkflowKey, OutputText)
        }
    } catch as Err {
        MsgBox("Connection failed. Ensure main.py and Ollama are running.`n" . Err.Message, "Edge AI Assistant", "Iconx")
    }
}

ShowResultWindow(TitleTag, BodyText) {
    ResGui := Gui("+AlwaysOnTop", "Result — " . TitleTag)
    ResGui.BackColor := "1E1E2E"
    ResGui.SetFont("s10 cCDD6F4", "Consolas")
    Box := ResGui.AddEdit("xm ym w540 r14 ReadOnly Background313244 cCDD6F4", BodyText)
    CopyBtn := ResGui.AddButton("xm y+10 w140", "Copy Output")
    CloseBtn := ResGui.AddButton("x+10 yp w140 Default", "Close")
    CopyBtn.OnEvent("Click", (*) => (A_Clipboard := BodyText))
    CloseBtn.OnEvent("Click", (*) => ResGui.Destroy())
    ResGui.OnEvent("Escape", (*) => ResGui.Destroy())
    ResGui.Show()
}

EscapeJson(Str) {
    Str := StrReplace(Str, "\", "\\")
    Str := StrReplace(Str, '"', '\"')
    Str := StrReplace(Str, "`r", "\r")
    Str := StrReplace(Str, "`n", "\n")
    Str := StrReplace(Str, "`t", "\t")
    return Str
}

ExtractJsonField(JsonStr, Key) {
    Needle := '"' . Key . '":"'
    StartPos := InStr(JsonStr, Needle)
    if !StartPos
        return JsonStr
    StartPos += StrLen(Needle)
    Result := ""
    i := StartPos
    Len := StrLen(JsonStr)
    while (i <= Len) {
        Ch := SubStr(JsonStr, i, 1)
        if (Ch = "\") {
            NextCh := SubStr(JsonStr, i + 1, 1)
            if (NextCh = "n")
                Result .= "`n"
            else if (NextCh = "r")
                Result .= "`r"
            else if (NextCh = "t")
                Result .= "`t"
            else if (NextCh = '"')
                Result .= '"'
            else if (NextCh = "\")
                Result .= "\"
            else
                Result .= NextCh
            i += 2
            continue
        }
        if (Ch = '"')
            break
        Result .= Ch
        i += 1
    }
    return Result
}