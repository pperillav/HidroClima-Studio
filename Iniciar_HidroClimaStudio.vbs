Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = dir

exePortable = dir & "\dist\HidroClimaStudio\HidroClimaStudio.exe"
pythonW = dir & "\.venv\Scripts\pythonw.exe"

If fso.FileExists(exePortable) Then
    shell.Run """" & exePortable & """", 1, False
ElseIf fso.FileExists(pythonW) Then
    shell.Run """" & pythonW & """ """ & dir & "\run_hidroclima.py""", 0, False
Else
    shell.Run "pythonw """ & dir & "\run_hidroclima.py""", 0, False
End If
