import '@/utils/browserHost'
import '@/styles/browser.css'

// 宿主接口必须先安装；页面及常驻订阅在模块求值时就会获取日志器。
void import('./main')
