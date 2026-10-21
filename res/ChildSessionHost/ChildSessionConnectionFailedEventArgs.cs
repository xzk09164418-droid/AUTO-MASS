using System;

namespace BetterGenshinImpact.Service.ChildSession
{
    public sealed class ChildSessionConnectionFailedEventArgs : EventArgs
    {
        public ChildSessionConnectionFailedEventArgs(
            string message,
            int errorCode,
            int? extendedErrorCode = null)
        {
            Message = message;
            ErrorCode = errorCode;
            ExtendedErrorCode = extendedErrorCode;
        }

        public string Message { get; private set; }

        public int ErrorCode { get; private set; }

        public int? ExtendedErrorCode { get; private set; }
    }
}
