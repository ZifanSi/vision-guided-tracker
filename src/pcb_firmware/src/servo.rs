use defmt::info;
use embassy_stm32::{
    Peri,
    gpio::{AnyPin, Level, Output, Speed},
};
use embassy_sync::{blocking_mutex::raw::NoopRawMutex, watch::Watch};
use embassy_time::{Duration, Ticker, Timer};

fn servo_angle_to_pulse_width_us(mut angle_deg: f32) -> u64 {
    let min_angle = -90.0;
    let max_angle = 90.0;

    if angle_deg < min_angle {
        angle_deg = min_angle;
    } else if angle_deg > max_angle {
        angle_deg = max_angle;
    }

    let min_pulse = 1040.0;
    let max_pulse = 2360.0;
    let pulse_width =
        min_pulse + (angle_deg - min_angle) / (max_angle - min_angle) * (max_pulse - min_pulse);
    pulse_width as u64
}

#[embassy_executor::task(pool_size = 2)]
pub async fn servo_task(
    pwm_pin: Peri<'static, AnyPin>,
    angle_deg_watch: &'static Watch<NoopRawMutex, f32, 1>,
) {
    let mut pwm_pin = Output::new(pwm_pin, Level::Low, Speed::Low);
    let mut receiver = angle_deg_watch.receiver().unwrap();
    let mut ticker = Ticker::every(Duration::from_hz(50));

    loop {
        ticker.next().await;

        let angle_deg = receiver.try_get().unwrap_or(0.0);
        let pulse_width_us = servo_angle_to_pulse_width_us(angle_deg);
        pwm_pin.set_high();
        Timer::after_micros(pulse_width_us).await;
        pwm_pin.set_low();
    }
}
