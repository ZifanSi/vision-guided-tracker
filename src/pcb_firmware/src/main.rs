#![no_std]
#![no_main]
#![feature(impl_trait_in_assoc_type)]
#![feature(associated_type_defaults)]
#![feature(try_blocks)]

use crate::{
    led::{arm_led_task, status_led_task},
    rpc::{GimbalRpc, rpc_task},
    servo::servo_task,
};

use {defmt_rtt as _, panic_probe as _};

mod led;
mod rpc;
mod servo;

use cortex_m::singleton;
use defmt::*;
use embassy_executor::Spawner;
use embassy_stm32::time::mhz;
use embassy_stm32::usart::{Config as UsartConfig, Uart};
use embassy_stm32::{bind_interrupts, peripherals, usart};
use embassy_sync::{blocking_mutex::raw::NoopRawMutex, watch::Watch};

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
    let gimbal_rpc = GimbalRpc {
        tilt_angle_deg_watch,
        pan_angle_deg_watch,
    };
    spawner.must_spawn(rpc_task(usart, gimbal_rpc));
}
