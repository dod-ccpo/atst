import stickybits from 'stickybits'

import DateSelector from '../date_selector'
import FormMixin from '../../mixins/form'
import Modal from '../../mixins/modal'
import MultiStepModalForm from './multi_step_modal_form'
import checkboxinput from '../checkbox_input'
import multicheckboxinput from '../multi_checkbox_input'
import optionsinput from '../options_input'
import SemiCollapsibleText from '../semi_collapsible_text'
import textinput from '../text_input'
import toggler from '../toggler'
import uploadinput from '../upload_input'

export default {
  name: 'base-form',
  components: {
    DateSelector,
    Modal,
    MultiStepModalForm,
    checkboxinput,
    multicheckboxinput,
    optionsinput,
    SemiCollapsibleText,
    textinput,
    toggler,
    uploadinput,
  },
  mixins: [FormMixin],
  directives: {
    sticky: {
      inserted: (el, binding) => {
        var customAttributes
        if (binding.expression) {
          customAttributes = JSON.parse(binding.expression)
        }
        stickybits(el, customAttributes)
      },
    },
  },
}
