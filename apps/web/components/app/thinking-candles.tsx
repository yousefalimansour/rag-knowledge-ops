import styles from './thinking-candles.module.css';

/** Animated "waiting for the model" loader — used while the Copilot SSE
 *  stream is open but no `token` event has arrived yet. Pure CSS, no JS
 *  ticking required. Source: Uiverse `_7754` candles. */
export function ThinkingCandles({ label = 'Thinking…' }: { label?: string }) {
  return (
    <div
      className="inline-flex items-center gap-3 py-2"
      role="status"
      aria-live="polite"
    >
      <div className={styles.scale}>
        <div className={styles.wrapper}>
          <div className={styles.candles}>
            <div className={styles.lightWave} />
            <div className={styles.candle1}>
              <div className={styles.candle1Body}>
                <div className={styles.candle1Eyes}>
                  <span className={styles.candle1EyesOne} />
                  <span className={styles.candle1EyesTwo} />
                </div>
                <div className={styles.candle1Mouth} />
              </div>
              <div className={styles.candle1Stick} />
            </div>
            <div className={styles.candle2}>
              <div className={styles.candle2Body}>
                <div className={styles.candle2Eyes}>
                  <div className={styles.candle2EyesOne} />
                  <div className={styles.candle2EyesTwo} />
                </div>
              </div>
              <div className={styles.candle2Stick} />
            </div>
            <div className={styles.candle2Fire} />
            <div className={styles.candleSmokeOne} />
            <div className={styles.candleSmokeTwo} />
          </div>
          <div className={styles.floor} />
        </div>
      </div>
      <span className="text-sm text-ink-muted">{label}</span>
    </div>
  );
}
