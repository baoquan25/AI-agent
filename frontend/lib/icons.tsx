import type { IconType } from 'react-icons';
import { VscFile, VscJson } from 'react-icons/vsc';
import {
  SiPython,
  SiTypescript,
  SiReact,
  SiCss,
  SiHtml5,
} from 'react-icons/si';
import { PiArrowFatDownFill } from 'react-icons/pi';
import { IoLogoJavascript, IoMdCode } from 'react-icons/io';
import { FaHashtag } from 'react-icons/fa';

export {
  VscChevronDown,
  VscChevronRight,
  VscChevronLeft,
  VscClose,
  VscError,
  VscAdd,
  VscLayoutSidebarLeft,
  VscLayoutPanel,
  VscLayoutSidebarRight,
  VscPlay,
  VscFiles,
  VscSearch,
  VscStopCircle,
  VscNewFile,
  VscNewFolder,
  VscRefresh,
  VscSaveAll,
  VscFile,
  VscListFlat,
} from 'react-icons/vsc';
export { SiPython, SiTypescript, SiReact, SiCss, SiHtml5 } from 'react-icons/si';
export { PiArrowFatDownFill } from 'react-icons/pi';
export { IoLogoJavascript, IoMdCode } from 'react-icons/io';
export { FaHashtag } from 'react-icons/fa';

export function getFileIcon(filename: string): { Icon: IconType; color: string } {
  const dot = filename.lastIndexOf('.');
  const ext = dot !== -1 ? filename.slice(dot).toLowerCase() : '';
  switch (ext) {
    case '.py':   return { Icon: SiPython,     color: '#4B8BBE' };
    case '.js':   return { Icon: IoLogoJavascript, color: '#F7DF1E' };
    case '.ts':   return { Icon: SiTypescript, color: '#3178C6' };
    case '.tsx':  return { Icon: SiReact,      color: '#61DAFB' };
    case '.jsx':  return { Icon: SiReact,      color: '#61DAFB' };
    case '.css':  return { Icon: FaHashtag,    color: '#1572B6' };
    case '.html': return { Icon: IoMdCode,     color: '#E34F26' };
    case '.md':   return { Icon: PiArrowFatDownFill, color: '#2196F3' };
    case '.json': return { Icon: VscJson,      color: '#CBCB41' };
    default:      return { Icon: VscFile,      color: 'inherit' };
  }
}
