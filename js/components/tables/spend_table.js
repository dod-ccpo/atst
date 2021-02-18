import { set } from 'vue/dist/vue'
import { formatDollars } from '../../lib/dollars'

export default {
  name: 'spend-table',

  props: {
    applications: Array,
  },

  data: function () {
    return {
      applicationsState: this.applications,
    }
  },

  created: function () {
    this.applicationsState.forEach((application) => {
      application.isVisible = false
    })
  },

  methods: {
    toggle: function (e, applicationIndex) {
      set(this.applicationsState, applicationIndex, {
        ...this.applicationsState[applicationIndex],
        isVisible: !this.applicationsState[applicationIndex].isVisible,
      })
    },

    formatDollars: function (value) {
      return formatDollars(value, false)
    },
  },
}
