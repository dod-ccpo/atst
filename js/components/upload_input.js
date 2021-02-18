import { buildUploader } from '../lib/upload'
import { emitFieldChange } from '../lib/emitters'
import inputValidations from '../lib/input_validations'

function uploadResponseOkay(response) {
  // check BlobUploadCommonResponse: https://docs.microsoft.com/en-us/javascript/api/@azure/storage-blob/blobuploadcommonresponse?view=azure-node-latest
  // The upload operation is a PUT that should return a 201
  // https://docs.microsoft.com/en-us/rest/api/storageservices/put-blob#status-code
  return response._response.status === 201
}

export default {
  name: 'uploadinput',

  props: {
    name: String,
    filename: {
      type: String,
    },
    initialObjectName: {
      type: String,
    },
    initialErrors: {
      type: Boolean,
      default: false,
    },
    portfolioId: {
      type: String,
    },
    sizeLimit: {
      type: Number,
    },
  },

  data: function () {
    return {
      hasInitialData: !!this.filename,
      attachment: this.filename || null,
      changed: false,
      uploadError: false,
      sizeError: false,
      filenameError: false,
      downloadLink: '',
      fileSizeLimit: this.sizeLimit,
      objectName: this.initialObjectName,
    }
  },

  created: async function () {
    if (this.hasInitialData) {
      this.downloadLink = await this.getDownloadLink(
        this.filename,
        this.objectName
      )
    }
  },

  methods: {
    addAttachment: async function (e) {
      this.clearErrors()

      const file = e.target.files[0]
      if (file.size > this.fileSizeLimit) {
        this.sizeError = true
        return
      }
      if (!this.validateFileName(file.name)) {
        this.filenameError = true
        return
      }

      const uploader = await this.getUploader()
      const response = await uploader.upload(file)
      if (uploadResponseOkay(response)) {
        this.attachment = file.name
        this.objectName = uploader.objectName
        this.$refs.attachmentFilename.value = file.name
        this.$refs.attachmentObjectName.value = response.objectName
        this.$refs.attachmentInput.disabled = true
        emitFieldChange(this)
        this.changed = true

        this.downloadLink = await this.getDownloadLink(
          file.name,
          uploader.objectName
        )
      } else {
        emitFieldChange(this)
        this.changed = true
        this.uploadError = true
      }
    },
    validateFileName: function (name) {
      const regex = inputValidations.restrictedFileName.match
      return regex.test(name)
    },
    removeAttachment: function (e) {
      e.preventDefault()
      this.attachment = null
      if (this.$refs.attachmentInput) {
        this.$refs.attachmentInput.value = null
        this.$refs.attachmentInput.disabled = false
      }
      this.clearErrors()
      this.changed = true

      emitFieldChange(this)
    },
    clearErrors: function () {
      this.uploadError = false
      this.sizeError = false
    },
    getUploader: async function () {
      return fetch(`/task_orders/${this.portfolioId}/upload_token`, {
        credentials: 'include',
      })
        .then((response) => response.json())
        .then(({ token, objectName, config, cloudProvider }) =>
          buildUploader(token, objectName, config, cloudProvider)
        )
    },
    getDownloadLink: async function (filename, objectName) {
      let baseUrl = window.location.href
      let relativeUrl = `/task_orders/${this.portfolioId}/download_link?filename=${filename}&objectName=${objectName}`
      let url = new URL(relativeUrl, baseUrl)
      const { downloadLink } = await fetch(url, {
        credentials: 'include',
      }).then((r) => r.json())
      return downloadLink
    },
  },

  computed: {
    baseName: function () {
      if (this.attachment) {
        return this.attachment.split(/[\\/]/).pop()
      }
    },
    hideInput: function () {
      return this.hasInitialData && !this.changed
    },
    showErrors: function () {
      return (
        (!this.changed && this.initialErrors) ||
        this.uploadError ||
        this.sizeError ||
        this.filenameError
      )
    },
    valid: function () {
      return !!this.attachment
    },
  },
}
