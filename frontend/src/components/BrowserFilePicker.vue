<script setup lang="ts">
import { ref, watch } from 'vue'
import { FolderOutlined, FileOutlined } from '@ant-design/icons-vue'
import { t } from '@/i18n'
import { invokeBrowserHost } from '@/composables/useBrowserHost'
import { browserPicker, finishLocalSelection } from '@/utils/browserFilePicker'

interface Entry {
  name: string
  path: string
  folder: boolean
}
interface Directory {
  directory: string
  parent: string
  entries: Entry[]
}
const address = ref('')
const selected = ref('')
const listing = ref<Directory>({ directory: '', parent: '', entries: [] })
const error = ref('')
const loading = ref(false)

async function browse(directory: string) {
  loading.value = true
  error.value = ''
  try {
    const result = await invokeBrowserHost<Directory>(
      'browseFiles',
      directory,
      browserPicker.extensions
    )
    listing.value = result
    address.value = result.directory
    selected.value = browserPicker.folder ? result.directory : ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}
async function confirm() {
  loading.value = true
  error.value = ''
  try {
    const path = await invokeBrowserHost<string>(
      'validatePath',
      selected.value,
      browserPicker.folder,
      browserPicker.extensions
    )
    finishLocalSelection(path)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}
watch(
  () => browserPicker.open,
  open => {
    if (open) void browse(listing.value.directory)
  }
)
</script>

<template>
  <a-modal
    v-model:open="browserPicker.open"
    :title="t(browserPicker.folder ? 'browser.folder' : 'browser.file')"
    :width="800"
    :confirm-loading="loading"
    :ok-button-props="{ disabled: !selected }"
    :ok-text="t('browser.select')"
    :cancel-text="t('browser.cancel')"
    @ok="confirm"
    @cancel="finishLocalSelection(null)"
  >
    <div class="browser-file-picker">
      <a-space-compact class="address-row">
        <a-button :disabled="loading || !listing.directory" @click="browse(listing.parent)">{{
          t('browser.up')
        }}</a-button>
        <a-input
          v-model:value="address"
          :placeholder="t('browser.address')"
          @press-enter="browse(address)"
        />
        <a-button :loading="loading" @click="browse(address)">{{ t('browser.go') }}</a-button>
      </a-space-compact>
      <a-alert v-if="error" :message="error" type="error" show-icon />
      <a-spin :spinning="loading">
        <div class="file-list">
          <a-empty v-if="!listing.entries.length" :description="t('browser.empty')" />
          <button
            v-for="entry in listing.entries"
            :key="entry.path"
            class="file-entry"
            :class="{ selected: selected === entry.path }"
            @click="entry.folder ? browse(entry.path) : (selected = entry.path)"
            @dblclick="!entry.folder && confirm()"
          >
            <FolderOutlined v-if="entry.folder" /><FileOutlined v-else />
            <span>{{ entry.name }}</span>
          </button>
        </div>
      </a-spin>
      <a-form layout="vertical">
        <a-form-item :label="t('browser.selected')">
          <a-input
            v-model:value="selected"
            :placeholder="t('browser.pathHint')"
            @press-enter="confirm"
          />
        </a-form-item>
      </a-form>
    </div>
  </a-modal>
</template>

<style scoped>
.browser-file-picker {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.address-row {
  display: flex;
  width: 100%;
}
.file-list {
  height: 320px;
  overflow: auto;
  border: 1px solid var(--ant-color-border);
  border-radius: 8px;
}
.file-entry {
  display: flex;
  gap: 12px;
  align-items: center;
  width: 100%;
  padding: 10px 16px;
  border: 0;
  text-align: left;
  background: transparent;
  color: var(--ant-color-text);
  cursor: pointer;
}
.file-entry:hover,
.file-entry.selected {
  background: var(--ant-color-fill-secondary);
}
.file-entry span {
  overflow-wrap: anywhere;
}
</style>
