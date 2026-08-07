(function defineObservatoryActionState(global) {
  'use strict';

  function create(control, labels = {}) {
    const idle = labels.idle || control.textContent || '';
    const pending = labels.pending || idle;
    const success = labels.success || idle;
    const failure = labels.failure || idle;

    function setState(state, text, disabled) {
      control.dataset.state = state;
      control.textContent = text;
      control.disabled = disabled;
    }

    async function run(action) {
      setState('pending', pending, true);
      try {
        const value = await action();
        setState('success', success, false);
        return Object.freeze({ok: true, value});
      } catch (error) {
        setState('error', failure, false);
        return Object.freeze({ok: false, error});
      }
    }

    function reset() {
      setState('idle', idle, false);
    }

    return Object.freeze({run, reset});
  }

  global.ObservatoryActionState = Object.freeze({create});
}(window));
