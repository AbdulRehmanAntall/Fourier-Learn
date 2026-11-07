/** "I'm Lost": one tap, or the L key (docs/frontend.md §6.7). It sits in the player's header so
 * it stays visible while paused, in fullscreen and on a tablet in portrait, and never ends up in
 * a menu. It is disabled only while a press is already being handled. */
export function ImLostButton({ disabled, onPress }: { disabled: boolean; onPress(): void }) {
  return (
    <button
      type="button"
      onClick={onPress}
      disabled={disabled}
      aria-keyshortcuts="L"
      title="I'm Lost (L)"
      className="h-11 shrink-0 rounded-full bg-amber-400 px-5 text-sm font-semibold text-black hover:bg-amber-300 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-60"
    >
      I&apos;m Lost
    </button>
  );
}
