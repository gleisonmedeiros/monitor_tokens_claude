Dim fso, shell, dir, venvPy, venvPyw

Set fso   = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

dir    = fso.GetParentFolderName(WScript.ScriptFullName)
venvPy  = dir & "\venv\Scripts\python.exe"
venvPyw = dir & "\venv\Scripts\pythonw.exe"

shell.CurrentDirectory = dir

' Cria venv se nao existir (usa py launcher para pegar melhor versao disponivel)
If Not fso.FileExists(venvPy) Then
    shell.Run "cmd /c py -m venv venv", 0, True
End If

' Instala/atualiza dependencias
shell.Run "cmd /c """ & venvPy & """ -m pip install -q -r requirements.txt", 0, True

' Inicia overlay sem janela de console
shell.Run """" & venvPyw & """ iniciar.pyw", 0, False
