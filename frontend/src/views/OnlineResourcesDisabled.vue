<template>
  <a-result
    status="info"
    title="本机构建已停用在线资源"
    sub-title="不再连接配置中心或下载在线外观。已有外观、本地导入与本地配置仍可使用。"
  >
    <template #extra
      ><a-button type="primary" @click="$router.push('/setting')">返回设置</a-button></template
    >
  </a-result>
</template>
