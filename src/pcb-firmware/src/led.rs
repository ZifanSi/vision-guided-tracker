use embassy_stm32::{
    Peri,
    gpio::{Level, Output, Speed},
    peripherals::{PC11, PD2},
};
use embassy_sync::{blocking_mutex::raw::CriticalSectionRawMutex, watch::Watch};
use embassy_time::{Duration, Ticker, Timer};

static ARM_LED_WATCH: Watch<CriticalSectionRawMutex, Level, 1> = Watch::new();
static STATUS_LED_WATCH: Watch<CriticalSectionRawMutex, Level, 1> = Watch::new();

pub fn set_arm_led(state: Level) {
    ARM_LED_WATCH.sender().send(state);
}

pub fn set_status_led(state: Level) {
    STATUS_LED_WATCH.sender().send(state);
}

#[embassy_executor::task]
pub async fn arm_led_task(arm_led: Peri<'static, PC11>) {
    let mut arm_led = Output::new(arm_led, Level::Low, Speed::Low);
    let mut receiver = ARM_LED_WATCH.receiver().unwrap();
    loop {
        let state = receiver.changed().await;
        arm_led.set_level(state);
    }
}

#[embassy_executor::task]
pub async fn status_led_task(status_led: Peri<'static, PD2>) {
    let mut status_led = Output::new(status_led, Level::Low, Speed::Low);
    let duration = Duration::from_hz(200);
    let period_us = duration.as_micros();
    let mut ticker = Ticker::every(duration);
    let on_time_us = (0.2f32 * period_us as f32) as u64;

    let mut receiver = STATUS_LED_WATCH.receiver().unwrap();
    loop {
        let state = receiver.try_get().unwrap_or(Level::Low);
        if state == Level::High {
            status_led.set_high();
            Timer::after_micros(on_time_us).await;
            status_led.set_low();
        } else {
            status_led.set_low();
        }
        ticker.next().await;
    }
}
