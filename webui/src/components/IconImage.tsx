import type { ImgHTMLAttributes, JSX } from "react";

interface IconImageProps extends Omit<ImgHTMLAttributes<HTMLImageElement>, "src"> {
  src: string;
  alt?: string;
}

export function IconImage({ src, alt, className, ...rest }: IconImageProps): JSX.Element {
  return (
    <img
      src={src}
      alt={alt ?? ""}
      className={className ? `icon ${className}` : "icon"}
      aria-hidden={alt ? undefined : true}
      {...rest}
    />
  );
}
