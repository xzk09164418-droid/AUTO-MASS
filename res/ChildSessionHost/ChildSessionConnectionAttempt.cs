using System;
using System.Threading.Tasks;

namespace BetterGenshinImpact.Service.ChildSession
{
    // 一次连接只对应一个结果，窗口自动连接与 HTTP 请求共享进行中的尝试。
    internal sealed class ChildSessionConnectionAttempt
    {
        private readonly object _gate = new object();
        private Task<bool> _pending;

        internal Task<bool> Run(Func<Task<bool>> connect)
        {
            lock (_gate)
            {
                if (_pending == null || _pending.IsCompleted)
                    _pending = connect();
                return _pending;
            }
        }
    }
}
