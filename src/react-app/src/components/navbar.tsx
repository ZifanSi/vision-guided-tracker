import { NavLink } from "react-router-dom";
import {
  Navbar as HeroUINavbar,
  NavbarContent,
  NavbarItem,
} from "@heroui/navbar";
import { link as linkStyles } from "@heroui/theme";
import clsx from "clsx";
import { useRocam } from "@/network/rocamProvider";
import { Button } from "@heroui/button";

export const Navbar = () => {
  const { apiClient } = useRocam();
  return (
    <HeroUINavbar maxWidth="full">
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
          color="danger"
          variant="bordered"
          onPress={() => apiClient?.arm()}
        >
          Emergency Stop
        </Button>
      </NavbarContent>
    </HeroUINavbar>
  );
};
