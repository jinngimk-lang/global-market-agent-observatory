(function wireRecoverableActions(global) {
  'use strict';

  global.addEventListener('DOMContentLoaded', () => {
    const refreshButton = global.document.getElementById('refresh-button');
    if (!refreshButton || typeof global.refreshAll !== 'function') return;

    refreshButton.removeEventListener('click', global.refreshAll);
    const refreshAction = global.ObservatoryActionState.create(refreshButton, {
      idle: '刷新',
      pending: '刷新中…',
      success: '已刷新',
      failure: '刷新失败 · 重试',
    });
    refreshButton.addEventListener('click', () => refreshAction.run(global.refreshAll));
  });
}(window));
