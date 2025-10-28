#![no_std]
#![no_main]
#![feature(impl_trait_in_assoc_type)]
#![feature(associated_type_defaults)]
#![feature(try_blocks)]

use crate::{
    led::{arm_led_task, set_arm_led, set_status_led, status_led_task},
    servo::servo_task,
};

use {defmt_rtt as _, panic_probe as _};

mod led;
mod servo;

use cortex_m::singleton;
use defmt::*;
use embassy_executor::Spawner;
use embassy_futures::join::join;
use embassy_stm32::gpio::{Level, Output, Speed};
use embassy_stm32::mode::Async;
use embassy_stm32::peripherals::{PC11, PD2};
use embassy_stm32::time::mhz;
use embassy_stm32::usart::{Config as UsartConfig, Uart};
use embassy_stm32::{Peri, bind_interrupts, peripherals, usart};
use embassy_sync::{
    blocking_mutex::raw::{CriticalSectionRawMutex, NoopRawMutex},
    watch::Watch,
};
use embassy_time::{Duration, Ticker, Timer};
use embedded_io_async::Write;
use micromath::F32Ext;

bind_interrupts!(struct Irqs {
    USART1 => usart::InterruptHandler<peripherals::USART1>;
});

#[embassy_executor::main]
async fn main(spawner: Spawner) {
    let config = {
        use embassy_stm32::rcc::mux::*;
        use embassy_stm32::rcc::*;
        let mut config = embassy_stm32::Config::default();

        config.rcc.hsi = false;
        config.rcc.hse = Some(Hse {
            freq: mhz(16),
            mode: HseMode::Oscillator,
        });
        config.rcc.sys = Sysclk::PLL1_P;

        config.rcc.pll_src = PllSource::HSE;
        config.rcc.pll = Some(Pll {
            prediv: PllPreDiv::DIV8,
            mul: PllMul::MUL96,
            divp: Some(PllPDiv::DIV2),
            divq: Some(PllQDiv::DIV4),
            divr: None,
        });

        config.rcc.ahb_pre = AHBPrescaler::DIV1;
        config.rcc.apb1_pre = APBPrescaler::DIV4;
        config.rcc.apb2_pre = APBPrescaler::DIV2;

        config.rcc.ls = LsConfig::off();

        config.rcc.mux.clk48sel = Clk48sel::PLL1_Q;

        config
    };
    let p = embassy_stm32::init(config);
    info!("Hello RoCam!");

    spawner.must_spawn(arm_led_task(p.PC11));
    spawner.must_spawn(status_led_task(p.PD2));

    let tilt_angle_deg_watch = singleton!(: Watch<NoopRawMutex, f32, 1> = Watch::new()).unwrap();
    let pan_angle_deg_watch = singleton!(: Watch<NoopRawMutex, f32, 1> = Watch::new()).unwrap();
    spawner.must_spawn(servo_task(p.PB5.into(), tilt_angle_deg_watch));
    spawner.must_spawn(servo_task(p.PB6.into(), pan_angle_deg_watch));

    let mut config = UsartConfig::default();
    config.baudrate = 115200;
    let usart = Uart::new(
        p.USART1, p.PA10, p.PA9, Irqs, p.DMA2_CH7, p.DMA2_CH5, config,
    )
    .unwrap();
    spawner.must_spawn(uart_task(usart));

    let mut ticker = Ticker::every(Duration::from_hz(50));
    let mut angle: f32 = 0.0;
    loop {
        ticker.next().await;
        // Calculate pulse width between 1000us and 2000us using sine wave
        // range: 500 - 2500us
        let angle2 = angle.sin() * 90.0;

        // tilt_angle_deg_watch.sender().send(angle2);

        // Increment angle (adjust speed by changing increment)
        angle += 0.02;
        if angle > 2.0 * core::f32::consts::PI {
            angle = 0.0;
        }
    }
}

#[embassy_executor::task]
async fn uart_task(mut uart: Uart<'static, Async>) {
    let mut buffer = [0u8; 128];
    loop {
        match uart.read_until_idle(&mut buffer).await {
            Ok(n) => {
                info!("Received: {:?}", &buffer[..n]);
                uart.write_all(&buffer[..n]).await.ok();
                uart.write_all("!".as_bytes()).await.ok();
            }
            Err(e) => error!("Error: {:?}", e),
        }
    }
}
