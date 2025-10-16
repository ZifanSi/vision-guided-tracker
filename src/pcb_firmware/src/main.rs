#![no_std]
#![no_main]
#![feature(impl_trait_in_assoc_type)]
#![feature(associated_type_defaults)]
#![feature(try_blocks)]

use {defmt_rtt as _, panic_probe as _};

use defmt::*;
use embassy_executor::Spawner;
use embassy_futures::join::join;
use embassy_stm32::gpio::{Level, Output, Speed};
use embassy_stm32::mode::Async;
use embassy_stm32::peripherals::PA3;
use embassy_stm32::time::mhz;
use embassy_stm32::usart::{Config as UsartConfig, Uart};
use embassy_stm32::{Peri, bind_interrupts, peripherals, usart};
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
    info!("Hello World!");

    spawner.spawn(led_task(p.PA3)).unwrap();

    let mut config = UsartConfig::default();
    config.baudrate = 115200;
    let usart = Uart::new(
        p.USART1, p.PA10, p.PA9, Irqs, p.DMA2_CH7, p.DMA2_CH5, config,
    )
    .unwrap();
    spawner.spawn(echo_task(usart)).unwrap();

    let mut pb5 = Output::new(p.PB5, Level::High, Speed::Low);
    let mut pb6 = Output::new(p.PB6, Level::High, Speed::Low);
    let mut ticker = Ticker::every(Duration::from_hz(50));
    let mut angle: f32 = 0.0;
    loop {
        ticker.next().await;
        // Calculate pulse width between 1000us and 2000us using sine wave
        // range: 500 - 2500us
        let tilt_pulse_width = (1200.0 + (300.0 * angle.sin())) as u64;
        let pan_pulse_width = (1500.0 + (500.0 * angle.cos())) as u64;

        let fut1 = async {
            pb5.set_low();
            Timer::after_micros(tilt_pulse_width).await;
            pb5.set_high();
        };
        let fut2 = async {
            pb6.set_low();
            Timer::after_micros(pan_pulse_width).await;
            pb6.set_high();
        };
        join(fut1, fut2).await;

        // Increment angle (adjust speed by changing increment)
        angle += 0.02;
        if angle > 2.0 * core::f32::consts::PI {
            angle = 0.0;
        }
    }
}

#[embassy_executor::task]
async fn echo_task(mut uart: Uart<'static, Async>) {
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

#[embassy_executor::task]
async fn led_task(pin: Peri<'static, PA3>) {
    let mut led = Output::new(pin, Level::High, Speed::Low);
    loop {
        Timer::after_millis(500).await;
        led.toggle();
    }
}
