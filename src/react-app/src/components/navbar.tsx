import { NavLink } from "react-router-dom";
import {
  Navbar as HeroUINavbar,
  NavbarContent,
  NavbarItem,
} from "@heroui/navbar";
import { link as linkStyles } from "@heroui/theme";
import clsx from "clsx";
import { Button } from "@heroui/button";
import { IconCancel, IconMaximize, IconMaximizeOff } from "@tabler/icons-react";

export const Navbar = () => {
  return (
    <HeroUINavbar
      maxWidth="full"
      classNames={{
        wrapper: "px-4",
      }}
    >
      <NavbarContent justify="start">
        <img src="/logo.png" alt="RoCam" className="h-8" />

        <div className="hidden lg:flex gap-4 justify-start ml-2">
          <NavbarItem>
            <NavLink
              className={({ isActive }: { isActive: boolean }) =>
                clsx(
                  linkStyles({ color: "foreground" }),
                  isActive ? "font-bold" : "text-gray-500"
                )
              }
              to={"/"}
            >
              Control
            </NavLink>
          </NavbarItem>
          <NavbarItem>
            <NavLink
              className={({ isActive }: { isActive: boolean }) =>
                clsx(
                  linkStyles({ color: "foreground" }),
                  isActive ? "font-bold" : "text-gray-500"
                )
              }
              to={"/recordings"}
            >
              Recordings
            </NavLink>
          </NavbarItem>
        </div>
      </NavbarContent>
      <NavbarContent justify="end">
        <Button
          radius="sm"
          variant="bordered"
          startContent={
            document.fullscreenElement ? <IconMaximizeOff /> : <IconMaximize />
          }
          onPress={() => {
            if (document.fullscreenElement) {
              document.exitFullscreen();
            } else {
              document.documentElement.requestFullscreen();
            }
          }}
        >
          {document.fullscreenElement ? "Exit Fullscreen" : "Fullscreen"}
        </Button>
        <Button
          radius="sm"
          color="danger"
          variant="bordered"
          startContent={<IconCancel />}
          onPress={() => {
            alert("Not implemented");
          }}
        >
          Emergency Stop
        </Button>
      </NavbarContent>
    </HeroUINavbar>
  );
};
