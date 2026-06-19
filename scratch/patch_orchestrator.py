import os

# 1. Patch orchestrator.py
filepath_orch = r"C:\Users\VikasVijigiri\Documents\TT_SQL_V2\backend\agent\agent\app\core\orchestrator.py"
with open(filepath_orch, 'r', encoding='utf-8') as f:
    content_orch = f.read()

target_orch = "        single_pass_mode: bool = False,"
replacement_orch = "        single_pass_mode: bool = True,"

if target_orch in content_orch:
    content_orch = content_orch.replace(target_orch, replacement_orch)
    print("Patched orchestrator.py default single_pass_mode (LF)")
else:
    target_orch_crlf = target_orch.replace("\n", "\r\n")
    replacement_orch_crlf = replacement_orch.replace("\n", "\r\n")
    if target_orch_crlf in content_orch:
        content_orch = content_orch.replace(target_orch_crlf, replacement_orch_crlf)
        print("Patched orchestrator.py default single_pass_mode (CRLF)")
    else:
        print("Failed to patch orchestrator.py!")

with open(filepath_orch, 'w', encoding='utf-8', newline='') as f:
    f.write(content_orch)

# 2. Patch router.py
filepath_router = r"C:\Users\VikasVijigiri\Documents\TT_SQL_V2\backend\agent\agent\app\custom\router.py"
with open(filepath_router, 'r', encoding='utf-8') as f:
    content_router = f.read()

target_router = """                orchestrator = SemanticDINOrchestrator(
                    db_directory=str(metadata_dir),
                    connection_string=conn_str,
                )"""

replacement_router = """                orchestrator = SemanticDINOrchestrator(
                    db_directory=str(metadata_dir),
                    connection_string=conn_str,
                    single_pass_mode=True,
                )"""

if target_router in content_router:
    content_router = content_router.replace(target_router, replacement_router)
    print("Patched router.py to explicitly pass single_pass_mode=True (LF)")
else:
    target_router_crlf = target_router.replace("\n", "\r\n")
    replacement_router_crlf = replacement_router.replace("\n", "\r\n")
    if target_router_crlf in content_router:
        content_router = content_router.replace(target_router_crlf, replacement_router_crlf)
        print("Patched router.py to explicitly pass single_pass_mode=True (CRLF)")
    else:
        print("Failed to patch router.py!")

with open(filepath_router, 'w', encoding='utf-8', newline='') as f:
    f.write(content_router)
