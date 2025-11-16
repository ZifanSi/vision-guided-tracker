import DefaultLayout from "@/layouts/default";
import { useRocam } from "@/network/rocamProvider";
import { useEffect } from "react";
import { Button } from "@heroui/button";
import { IconChevronLeft, IconChevronRight, IconChevronUp, IconChevronDown, IconHome } from '@tabler/icons-react';

export default function ControlPage() {
  const { apiClient, status, error } = useRocam();

  useEffect(() => {
    if (error) {
      console.error(error);
    }
  }, [error]);

  return (
    <DefaultLayout className="flex items-stretch">
      <div className="grid gap-4 m-4 mt-0 grid-cols-[auto_1fr] grid-rows-[1fr_auto] min-w-0 w-full">
        <div className="bg-gray-100 aspect-[9/16] rounded-lg flex items-center justify-center row-span-2">
          Video Preview here
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
              radius="sm"
              color="danger"
              variant="bordered"
              onPress={() => apiClient?.arm()}
            >
              Arm
            </Button>
            <Button
              radius="sm"
              color="primary"
              variant="bordered"
              onPress={() => apiClient?.disarm()}
            >
              Disarm
            </Button>
          </div>
          <div className="grid gap-2 mt-4 grid-cols-3 grid-rows-3 w-fit">
            <div></div>
            <Button radius="sm" isIconOnly size="lg" variant="flat" disabled={status?.armed} onPress={() => apiClient?.manualMove("up")}><IconChevronUp/></Button>
            <div></div>
            <Button radius="sm" isIconOnly size="lg" variant="flat" disabled={status?.armed} onPress={() => apiClient?.manualMove("left")}><IconChevronLeft/></Button>
            <Button radius="sm" isIconOnly size="lg" variant="flat" disabled={status?.armed} onPress={() => apiClient?.manualMoveTo(0, 0)}><IconHome/></Button>
            <Button radius="sm" isIconOnly size="lg" variant="flat" disabled={status?.armed} onPress={() => apiClient?.manualMove("right")}><IconChevronRight/></Button>
            <div></div>
            <Button radius="sm" isIconOnly size="lg" variant="flat" disabled={status?.armed} onPress={() => apiClient?.manualMove("down")}><IconChevronDown/></Button>
            <div></div>
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
