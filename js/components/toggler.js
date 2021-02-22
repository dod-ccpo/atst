import optionsinput from './options_input'
import textinput from './text_input'
import BaseForm from './forms/base_form'

export default {
  name: 'toggler',

  props: {
    initialSelectedSection: {
      type: String,
      default: null,
    },
  },

  components: {
    optionsinput,
    textinput,
    BaseForm,
    toggler: this,
  },

  data: function () {
    return {
      selectedSection: this.initialSelectedSection,
    }
  },

  methods: {
    toggleSection: function (sectionName) {
      if (this.selectedSection === sectionName) {
        this.selectedSection = null
      } else {
        this.selectedSection = sectionName
      }
    },
  },
}
