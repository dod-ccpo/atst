import 'svg-innerhtml'
import 'babel-polyfill'
import ally from 'ally.js'

import classes from '../styles/atat.scss'
import Vue from 'vue/dist/vue'
import VTooltip from 'v-tooltip'
import stickybits from 'stickybits'

import Accordion from './components/accordion'
import AccordionList from './components/accordion_list'
import dodlogin from './components/dodlogin'
import optionsinput from './components/options_input'
import multicheckboxinput from './components/multi_checkbox_input'
import textinput from './components/text_input'
import checkboxinput from './components/checkbox_input'
import toggler from './components/toggler'
import ApplicationEnvironments from './components/forms/new_application/environments'
import MultiStepModalForm from './components/forms/multi_step_modal_form'
import uploadinput from './components/upload_input'
import Modal from './mixins/modal'
import SpendTable from './components/tables/spend_table'
import LocalDatetime from './components/local_datetime'
import { isNotInVerticalViewport } from './lib/viewport'
import DateSelector from './components/date_selector'
import SidenavToggler from './components/sidenav_toggler'
import BaseForm from './components/forms/base_form'
import DeleteConfirmation from './components/delete_confirmation'
import NewEnvironment from './components/forms/new_environment'
import SemiCollapsibleText from './components/semi_collapsible_text'
import ToForm from './components/forms/to_form'
import ClinFields from './components/clin_fields'
import PopDateRange from './components/pop_date_range'
import ToggleMenu from './components/toggle_menu'
import ExpandSidenav from './mixins/expand_sidenav'

Vue.config.productionTip = false

Vue.use(VTooltip)

Vue.mixin(Modal)
Vue.mixin(ExpandSidenav)

const app = new Vue({
  el: '#app-root',
  components: {
    Accordion,
    AccordionList,
    dodlogin,
    toggler,
    optionsinput,
    multicheckboxinput,
    textinput,
    checkboxinput,
    ApplicationEnvironments,
    SpendTable,
    LocalDatetime,
    MultiStepModalForm,
    uploadinput,
    DateSelector,
    SidenavToggler,
    BaseForm,
    DeleteConfirmation,
    NewEnvironment,
    SemiCollapsibleText,
    ToForm,
    ClinFields,
    PopDateRange,
    ToggleMenu,
  },

  data: function () {
    return {
      sidenavExpanded: this.defaultVisible,
    }
  },

  mounted: function () {
    this.$on('modalOpen', (data) => {
      if (data['isOpen']) {
        document.body.className += ' modal-open'
        this.activeModal = data['name']

        var handler = ally.maintain.disabled({
          filter: `#${this.modalId}`,
        })

        this.allyHandler = handler
      } else {
        this.activeModal = null
        if (this.allyHandler) {
          this.allyHandler.disengage()
          this.allyHandler = null
        }
        document.body.className = document.body.className.replace(
          ' modal-open',
          ''
        )
      }
    })

    const modalOpen = document.querySelector('#modalOpen')

    if (modalOpen) {
      const modal = modalOpen.getAttribute('data-modal')
      this.openModal(modal)
    }

    ally.query.focusable().forEach(function (el) {
      el.addEventListener('focus', function () {
        if (isNotInVerticalViewport(el)) {
          el.scrollIntoView({ block: 'center' })
        }
      })
    })

    this.$on('sidenavToggle', (data) => {
      this.sidenavExpanded = data
    })
  },
  delimiters: ['!{', '}'],

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

  methods: {
    logout: function (e) {
      // clear all cookies
      var cookies = document.cookie.split(';')

      for (var i = 0; i < cookies.length; i++) {
        document.cookie =
          cookies[i].split('=')[0] + '=; expires=Thu, 01 Jan 1970 00:00:01 GMT;'
      }
    },
  },
})
