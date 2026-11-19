<template>
  <header class="terminal-bar">
    <div class="window-lights" aria-hidden="true"><i></i><i></i><i></i></div>
    <slot />
    <slot name="actions" />
  </header>
</template>
