import Vue from 'vue'

import DateSelector from '../date_selector'

describe('DateSelector', () => {
  const component = new Vue(DateSelector).$mount()

  describe('isDateValid', () => {
    it('returns true when a valid date', () => {
      component.day = 4
      component.month = 8
      component.year = 1776

      expect(component.isDateValid).toEqual(true)
    })

    it('returns false when an invalid date', () => {
      component.day = 32
      component.month = 13
      component.year = 2019

      expect(component.isDateValid).toEqual(false)
    })

    it('returns false when parts of the date are missing', () => {
      component.day = 31
      component.year = 2019

      expect(component.isDateValid).toEqual(false)
    })
  })

  describe('daysMaxCalculation', () => {
    it('calculates correctly for each month', () => {
      component.year = null

      let months = {
        1: 31,
        2: 29,
        3: 31,
        4: 30,
        5: 31,
        6: 30,
        7: 31,
        8: 31,
        9: 30,
        10: 31,
        11: 30,
        12: 31,
      }

      for (var month in months) {
        component.month = parseInt(month)
        expect(component.daysMaxCalculation).toEqual(months[month])
      }
    })

    it('takes year or lack of year into account and calculates leap years', () => {
      component.month = 2

      component.year = null
      expect(component.daysMaxCalculation).toEqual(29)

      component.year = 2019
      expect(component.daysMaxCalculation).toEqual(28)

      component.year = 2016
      expect(component.daysMaxCalculation).toEqual(29)
    })
  })

  describe('isMonthValid', () => {
    it('returns false when over 12', () => {
      component.month = 13
      expect(component.isMonthValid).toEqual(false)
    })

    it('returns true when between 1 and 12', () => {
      component.month = 3
      expect(component.isMonthValid).toEqual(true)
    })

    it('returns false when null', () => {
      component.month = null
      expect(component.isMonthValid).toEqual(false)
    })
  })

  describe('isDayValid', () => {
    it('returns true when 31 and no month', () => {
      component.day = 31
      component.month = null
      expect(component.isDayValid).toEqual(true)
    })

    it('returns false when 31 and in February', () => {
      component.day = 31
      component.month = 2
      expect(component.isDayValid).toEqual(false)
    })

    it('returns false when 32 and no month', () => {
      component.day = 32
      component.month = null
      expect(component.isDayValid).toEqual(false)
    })

    it('returns false when null', () => {
      component.day = null
      expect(component.isDayValid).toEqual(false)
    })
  })

  describe('isWithinDateRange', () => {
    beforeEach(() => {
      component.day = 24
      component.month = 1
      component.year = 2019
    })

    it('always returns true when no mindate or maxdate', () => {
      expect(component.isWithinDateRange).toEqual(true)
    })

    it('handles mindate only', () => {
      component.mindate = '2019-01-25'
      expect(component.isWithinDateRange).toEqual(false)

      component.mindate = '2014-01-25'
      expect(component.isWithinDateRange).toEqual(true)
    })

    it('handles maxdate only', () => {
      component.maxdate = '2019-01-25'
      expect(component.isWithinDateRange).toEqual(true)

      component.maxdate = '2014-01-25'
      expect(component.isWithinDateRange).toEqual(false)
    })

    it('handles mindate and maxdate', () => {
      component.mindate = '2019-01-25'
      component.maxdate = '2019-02-28'
      expect(component.isWithinDateRange).toEqual(false)

      component.mindate = '2013-01-25'
      component.maxdate = '2016-02-28'
      expect(component.isWithinDateRange).toEqual(false)

      component.mindate = '2014-01-25'
      component.maxdate = '2020-02-28'
      expect(component.isWithinDateRange).toEqual(true)
    })
  })

  describe('isYearValid', () => {
    it('returns false if year is null', () => {
      component.year = null
      expect(component.isYearValid).toEqual(false)
    })

    it('returns true if year is present', () => {
      component.year = new Date().getFullYear()
      component.mindate = ''
      component.maxdate = ''
      expect(component.isYearValid).toEqual(true)
    })

    it('returns true when year is between min and max years', () => {
      component.year = '2019'
      component.mindate = '2018-01-01'
      component.maxdate = '2019-12-31'
      expect(component.isYearValid).toEqual(true)
    })

    it('returns false when year is outside of min and max years', () => {
      component.year = '2020'
      component.mindate = '2018-01-01'
      component.maxdate = '2019-01-01'
      expect(component.isYearValid).toEqual(false)
    })
  })

  describe('formattedDate', () => {
    it('returns null if not all parts are present', () => {
      component.day = null
      component.month = 1
      component.year = 1988

      expect(component.formattedDate).toBeNull()
    })

    it('joins date components into a JS date', () => {
      component.mindate = null
      component.maxdate = null
      component.day = 22
      component.month = 1
      component.year = 1988

      expect(component.formattedDate).toEqual('01/22/1988')
    })
  })

  describe('isDateComplete', () => {
    it('returns true if all fields are completed', () => {
      component.day = 22
      component.month = 1
      component.year = 1988
      expect(component.isDateComplete).toEqual(true)
    })

    it('returns false if all fields are not completed', () => {
      component.day = 22
      component.month = 1
      component.year = 19
      expect(component.isDateComplete).toEqual(false)
    })
  })

  describe('minError', () => {
    it('returns true if the date is before mindate', () => {
      component.mindate = new Date('2020-01-01')
      component.day = 1
      component.month = 1
      component.year = 2000
      expect(component.minError).toEqual(true)
    })

    it('returns fals if the date is after mindate', () => {
      component.mindate = new Date('2020-01-01')
      component.day = 1
      component.month = 1
      component.year = 2025
      expect(component.minError).toEqual(false)
    })
  })

  describe('maxError', () => {
    it('returns true if the date is after maxdate', () => {
      component.maxdate = new Date('2020-01-01')
      component.day = 1
      component.month = 1
      component.year = 2025
      expect(component.maxError).toEqual(true)
    })

    it('returns false if the date is before maxdate', () => {
      component.maxdate = new Date('2020-01-01')
      component.day = 1
      component.month = 1
      component.year = 2005
      expect(component.maxError).toEqual(false)
    })
  })

  describe('outsideRange', () => {
    it('should return true if the date is before the minrange', () => {
      component.minrange = '2020-01-01'
      component.maxrange = '2025-01-01'
      component.day = 1
      component.month = 1
      component.year = 2005
      expect(component.outsideRange).toEqual(true)
    })

    it('should return true if the date is after the maxrange', () => {
      component.minrange = '2020-01-01'
      component.maxrange = '2025-01-01'
      component.day = 1
      component.month = 1
      component.year = 2030
      expect(component.outsideRange).toEqual(true)
    })

    it('should return false if the date is betwen minrange and maxrange', () => {
      component.minrange = '2020-01-01'
      component.maxrange = '2025-01-01'
      component.day = 1
      component.month = 1
      component.year = 2022
      expect(component.outsideRange).toEqual(false)
    })
  })
})
