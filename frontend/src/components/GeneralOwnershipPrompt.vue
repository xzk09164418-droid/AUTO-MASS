<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useGeneralOwnership } from '@/composables/useGeneralOwnership'

const { t } = useI18n()
const router = useRouter()
const { prompt, error, busy, answer } = useGeneralOwnership()
async function choose(edit: boolean) {
  const scriptId = await answer(edit)
  if (scriptId) await router.push(`/scripts/${encodeURIComponent(scriptId)}/edit/general`)
}
</script>

<template>
  <a-modal
    :open="!!prompt"
    centered
    :closable="false"
    :mask-closable="false"
    :keyboard="false"
    :title="t('generalOwnership.title')"
    :ok-text="t('generalOwnership.edit')"
    :cancel-text="t('generalOwnership.keep')"
    :confirm-loading="busy"
    :cancel-button-props="{ disabled: busy }"
    @ok="choose(true)"
    @cancel="choose(false)"
  >
    <p>{{ t('generalOwnership.reason', { name: prompt?.scriptName }) }}</p>
    <p>{{ t(prompt?.automated ? 'generalOwnership.scheduled' : 'generalOwnership.manual') }}</p>
    <a-alert v-if="error" type="error" show-icon :message="error" />
  </a-modal>
</template>
