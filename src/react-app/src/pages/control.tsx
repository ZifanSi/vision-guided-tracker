import { useEffect } from "react";
import { Button } from "@heroui/button";
import {
  IconChevronLeft,
  IconChevronRight,
  IconChevronUp,
  IconChevronDown,
  IconHome,
} from "@tabler/icons-react";

import { useRocam } from "@/network/rocamProvider";
import DefaultLayout from "@/layouts/default";
import { useMeasure } from "react-use";

export default function ControlPage() {
  const { apiClient, status, error } = useRocam();
  const [streamContainerRef, { width, height }] = useMeasure<HTMLDivElement>();

  useEffect(() => {
    if (error) {
      console.error(error);
    }
  }, [error]);

  return (
    <DefaultLayout className="flex items-stretch">
      <div className="grid gap-4 m-4 mt-0 grid-cols-[auto_1fr] grid-rows-[1fr_auto] min-w-0 w-full">
        <div
          ref={streamContainerRef}
          className="bg-gray-100 aspect-[9/16] rounded-lg flex items-center justify-center row-span-2"
        >
          <p>Live Stream Loading.....</p>
          <img
            className="absolute rotate-90 rounded-lg"
            src={status?.preview ? `data:image/jpeg;base64,${status.preview}` : undefined}
            style={{ width: height, height: width }}
          />
        </div>

        <div className="bg-gray-100 rounded-lg p-4 font-mono">
          <p>
            <span className="font-medium text-gray-500">Status: </span>
            {status?.armed ? (
              <span className="text-red-500">Armed</span>
            ) : (
              <span>Disarmed</span>
            )}
          </p>
          <div className="flex gap-4 font-mono mt-4">
            <div>
              <p className="text-sm font-medium text-gray-500 font-mono">
                TILT
              </p>
              <p className="w-16">{formatDegrees(status?.tilt)}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500 font-mono">PAN</p>
              <p className="w-16">{formatDegrees(status?.pan)}</p>
            </div>
          </div>
        </div>

        <div className="bg-gray-100 rounded-lg p-4">
          <div className="flex gap-4">
            <Button
              color="danger"
              radius="sm"
              variant="bordered"
              onPress={() => apiClient?.arm()}
            >
              Arm
            </Button>
            <Button
              color="primary"
              radius="sm"
              variant="bordered"
              onPress={() => apiClient?.disarm()}
            >
              Disarm
            </Button>
          </div>
          <div className="grid gap-2 mt-4 grid-cols-3 grid-rows-3 w-fit">
            <div />
            <Button
              isIconOnly
              disabled={status?.armed}
              radius="sm"
              size="lg"
              variant="flat"
              onPress={() => apiClient?.manualMove("up")}
            >
              <IconChevronUp />
            </Button>
            <div />
            <Button
              isIconOnly
              disabled={status?.armed}
              radius="sm"
              size="lg"
              variant="flat"
              onPress={() => apiClient?.manualMove("left")}
            >
              <IconChevronLeft />
            </Button>
            <Button
              isIconOnly
              disabled={status?.armed}
              radius="sm"
              size="lg"
              variant="flat"
              onPress={() => apiClient?.manualMoveTo(0, 0)}
            >
              <IconHome />
            </Button>
            <Button
              isIconOnly
              disabled={status?.armed}
              radius="sm"
              size="lg"
              variant="flat"
              onPress={() => apiClient?.manualMove("right")}
            >
              <IconChevronRight />
            </Button>
            <div />
            <Button
              isIconOnly
              disabled={status?.armed}
              radius="sm"
              size="lg"
              variant="flat"
              onPress={() => apiClient?.manualMove("down")}
            >
              <IconChevronDown />
            </Button>
            <div />
          </div>
        </div>
      </div>
    </DefaultLayout>
  );
}

function formatDegrees(degrees: number | undefined) {
  if (degrees === undefined) return "N/A";

  return `${Math.round(degrees * 10) / 10}°`;
}
