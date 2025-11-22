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
use embassy_executor::{Executor, InterruptExecutor};
use embassy_stm32::interrupt::{InterruptExt, Priority};
use embassy_stm32::time::mhz;
use embassy_stm32::usart::Config as UsartConfig;
use embassy_stm32::{bind_interrupts, peripherals, usart};
use embassy_stm32::{interrupt, usart::BufferedUart};
use embassy_sync::{blocking_mutex::raw::CriticalSectionRawMutex, watch::Watch};

#[cortex_m_rt::entry]
fn main() -> ! {
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

    let tilt_angle_deg_watch =
        singleton!(: Watch<CriticalSectionRawMutex, f32, 1> = Watch::new()).unwrap();
    let pan_angle_deg_watch =
        singleton!(: Watch<CriticalSectionRawMutex, f32, 1> = Watch::new()).unwrap();

    // High priority executor
    {
        static EXECUTOR: InterruptExecutor = InterruptExecutor::new();
        #[embassy_stm32::interrupt]
        unsafe fn USART2() {
            unsafe { EXECUTOR.on_interrupt() }
        }

        interrupt::USART2.set_priority(Priority::P0);
        let spawner = EXECUTOR.start(interrupt::USART2);

        spawner.spawn(servo_task(p.PB5.into(), 49.0, true, tilt_angle_deg_watch).unwrap());
        spawner.spawn(servo_task(p.PB6.into(), -7.0, false, pan_angle_deg_watch).unwrap());
    }

    // Low priority executor
    {
        let executor_low = singleton!(: Executor = Executor::new()).unwrap();
        executor_low.run(|spawner| {
            spawner.spawn(arm_led_task(p.PC11).unwrap());
            spawner.spawn(status_led_task(p.PD2).unwrap());

            bind_interrupts!(struct Irqs {
                USART1 => usart::BufferedInterruptHandler<peripherals::USART1>;
            });
            let mut config = UsartConfig::default();
            config.baudrate = 115200;
            let tx_buffer = singleton!(: [u8; 64] = [0; 64]).unwrap();
            let rx_buffer = singleton!(: [u8; 64] = [0; 64]).unwrap();
            let usart =
                BufferedUart::new(p.USART1, p.PA10, p.PA9, tx_buffer, rx_buffer, Irqs, config)
                    .unwrap();

            let gimbal_rpc = GimbalRpc {
                tilt_angle_deg_watch,
                pan_angle_deg_watch,
            };
            spawner.spawn(rpc_task(usart, gimbal_rpc).unwrap());
        })
    }
}
