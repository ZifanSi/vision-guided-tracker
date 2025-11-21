use defmt::{error, info};
use embassy_stm32::{
    gpio::Level,
    usart::{BufferedUart, Error as UartError},
};
use embassy_sync::{blocking_mutex::raw::CriticalSectionRawMutex, watch::Watch};
use embedded_io_async::{Read, Write};
use firmware_common_new::rpc::{gimbal_rpc::*, half_duplex_serial::HalfDuplexSerial};

use crate::led::{set_arm_led, set_status_led};

pub struct GimbalRpc {
    pub tilt_angle_deg_watch: &'static Watch<CriticalSectionRawMutex, f32, 1>,
    pub pan_angle_deg_watch: &'static Watch<CriticalSectionRawMutex, f32, 1>,
}

impl GimbalRpcServer for GimbalRpc {
    async fn arm_led(&mut self, enabled: bool) -> ArmLedResponse {
        set_arm_led(if enabled { Level::High } else { Level::Low });
        ArmLedResponse {}
    }

    async fn status_led(&mut self, enabled: bool) -> StatusLedResponse {
        set_status_led(if enabled { Level::High } else { Level::Low });
        StatusLedResponse {}
    }

    async fn move_deg(&mut self, mut tilt: f32, mut pan: f32) -> MoveDegResponse {
        if tilt > 90.0 {
            tilt = 90.0;
        } else if tilt < 0.0 {
            tilt = 0.0;
        }
        if pan > 45.0 {
            pan = 45.0;
        } else if pan < -45.0 {
            pan = -45.0;
        }
        self.tilt_angle_deg_watch.sender().send(tilt);
        self.pan_angle_deg_watch.sender().send(pan);
        MoveDegResponse {}
    }

    async fn measure_deg(&mut self) -> MeasureDegResponse {
        MeasureDegResponse {
            tilt: self
                .tilt_angle_deg_watch
                .anon_receiver()
                .try_get()
                .unwrap_or(0.0),
            pan: self
                .pan_angle_deg_watch
                .anon_receiver()
                .try_get()
                .unwrap_or(0.0),
        }
    }
}

#[embassy_executor::task]
pub async fn rpc_task(uart: BufferedUart<'static>, mut rpc: GimbalRpc) {
    struct SerialWrapper(BufferedUart<'static>);

    impl HalfDuplexSerial for SerialWrapper {
        type Error = UartError;

        async fn read(&mut self, buf: &mut [u8]) -> Result<usize, Self::Error> {
            self.0.read(buf).await
        }

        async fn write(&mut self, buf: &[u8]) -> Result<usize, Self::Error> {
            self.0.write(buf).await
        }

        async fn clear_read_buffer(&mut self) -> Result<(), Self::Error> {
            Ok(())
        }
    }

    let mut serial = SerialWrapper(uart);

    info!("RPC server started");
    loop {
        let err = rpc.run_server(&mut serial).await.unwrap_err();
        error!("Error while running rpc server: {:?}", err);
    }
}
