"""只读查看恢复状态，或由操作者明确解除故障暂停；不执行注销或重启。"""

import argparse
import importlib.util
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "resume"))
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--acknowledge-fault-resolved", action="store_true")
    args = parser.parse_args()
    module_path = args.root / "app/services/desktop_recovery_store.py"
    spec = importlib.util.spec_from_file_location("recovery_store", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("找不到恢复记录模块")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    store = module.DesktopRecoveryStore(args.root)
    if args.action == "resume":
        if not args.acknowledge_fault_resolved:
            parser.error("必须明确确认故障已处理；该动作会重置一次自动重启额度")
        store.tasks()  # 身份清单不可读时不能猜测要启动哪个队列。
        store.write("control.json", {"phase": "recovering", "reboot_used": False})
        print("已请求人工恢复；主桌面仍会检查 UU；实机测试模式还会检查回退保护。")
    else:
        print(json.dumps(store.control(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
