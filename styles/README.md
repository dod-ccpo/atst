# Styling ATAT

ATAT's user interface components are based on the (U.S. Web Design System)[https://designsystem.digital.gov/components/]. Please refer there when deciding how to implement a UI feature.

## CSS Architecture
### (Copied from https://github.com/uswds/uswds#css-architecture)
## CSS architecture

* The CSS foundation of this site is built with the **[Sass](https://sass-lang.com)** preprocessor language.
* Uses **[Bourbon](http://bourbon.io/)** for its simple and lightweight Sass mixin library, and the **[Neat](http://neat.bourbon.io/)** library for the grid framework. Bourbon and Neat are open-source products from **[thoughtbot](https://thoughtbot.com/)**.
* The CSS organization and naming conventions follow **[18F’s CSS Front End Guide](https://frontend.18f.gov/css/)**.
* CSS selectors are **prefixed** with `usa` (For example: `.usa-button`). This identifier helps the design system avoid conflicts with other styles on a site which are not part of the U.S. Web Design System.
* Uses a **[modified BEM](https://frontend.18f.gov/css/naming/)** approach created by 18F for naming CSS selectors. Objects in CSS are separated by single dashes. Multi-word objects are separated by an underscore (For example: `.usa-button-cool_feature-active`).
* Uses **modular CSS** for scalable, modular, and flexible code.
* Uses **nesting** when appropriate. Nest minimally with up to two levels of nesting.
* Hard-coded magic numbers are avoided and, if necessary, defined in the `core/variables` scss file.
* Media queries are built **mobile first**.
* **Spacing units** are as much as possible defined as rem or em units so they scale appropriately with text size. Pixels can be used for detail work and should not exceed 5px (For example: 3px borders).

**For more information, visit:**
[18F’s CSS Front End Guide](https://frontend.18f.gov/css/)

Overrides and Modifications
---

When making modifications to the default USWDS components, please refer to the original source, and make a `.scss` file of the same name. Annotate the top of the file with a reference to the USWDS documentation and source code.

Row/Column System
---

A simple, flexbox-powered row/column system.

```
<div class='row'>
  <div class='col'></div>
  <div class='col'></div>
  <div class='col'></div>
</div>
```

To make a column expand to fill up all available space relative to its sibling columns:

```
<div class='row'>
  <div class='col col--grow'></div>
  <div class='col'></div>
  <div class='col'></div>
</div>
```

To add uniform padding to rows and columns:

```
<div class='row row--pad'>
  <div class='col col--pad'></div>
  <div class='col col--pad'></div>
  <div class='col col--pad'></div>
</div>
```

Layouts and behaviors for specific row/col use cases should be handled on a case by case basis:

```
<div class='row row--pad foo'>
  <div class='col col--pad foo__bar'></div>
  <div class='col col--pad'></div>
  <div class='col col--pad'></div>
</div>

...

.foo.row {
  .col {
    flex: 1;
  }
  .foo__bar {
    flex: 2;
  }
}
```

Page templates that inherit from the `base_private.html` template should render `.col` elements at their top level, with no other wrapping elements.
