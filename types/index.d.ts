export type PetStatus = 'working' | 'done' | 'interrupted' | 'idle'

/** What the person is being asked for while Claude waits on them. */
export type Attention = 'permission' | 'question'

declare module 'claude-code' {
  interface PluginState {
    'edge-claw': { isOut: boolean }
  }
}
