export default {
  methods: {
    closeModal: function (name) {
      this.$root.$emit('modalOpen', { isOpen: false, name: name })
    },

    openModal: function (name) {
      this.$root.$emit('modalOpen', { isOpen: true, name: name })
    },

    // TODO: activeModal should be tracked on the root
    handleModalOpen: function (event) {
      if (!event.isOpen) {
        this.activeModal = null
      }
    },
  },

  mounted: function () {
    this.$root.$on('modalOpen', this.handleModalOpen)
  },

  data: function () {
    // TODO: only the root component should know about the activeModal
    return {
      activeModal: null,
      allyHandler: null,
    }
  },
  computed: {
    modalId: function () {
      return !!this.activeModal ? `modal--${this.activeModal}` : null
    },
  },
}
