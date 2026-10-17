' Silent launcher: runs a command with NO visible window.
' Windows scheduled tasks create console windows for console apps
' (python.exe, pwsh.exe). This wrapper runs them invisibly.

' Usage: wscript.exe "silent_launch.vbs" <command> [args...]
' The command runs detached, window style 0 (hidden), no wait.

Dim shell, cmd
Set shell = CreateObject("WScript.Shell")

' Reconstruct the command from all arguments
cmd = ""
For i = 0 To WScript.Arguments.Count - 1
    If i > 0 Then cmd = cmd & " "
    cmd = cmd & """" & WScript.Arguments(i) & """"
Next

' 0 = hidden window, False = don't wait for completion
shell.Run cmd, 0, False
