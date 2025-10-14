#![no_std]
#![no_main]
#![feature(impl_trait_in_assoc_type)]
#![feature(associated_type_defaults)]
#![feature(try_blocks)]

use {defmt_rtt as _, panic_probe as _};

use defmt::*;
use embassy_executor::Spawner;
use embassy_stm32::Peri;
use embassy_stm32::gpio::{Level, Output, Speed};
use embassy_stm32::peripherals::PA3;
use embassy_stm32::time::mhz;
use embassy_time::Timer;

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
    info!("Hello World!");

    spawner.spawn(led_task(p.PA3)).unwrap();
}

#[embassy_executor::task]
async fn led_task(pin: Peri<'static, PA3>) {
    let mut led = Output::new(pin, Level::High, Speed::Low);
    loop {
        Timer::after_millis(500).await;
        led.toggle();
    }
}
