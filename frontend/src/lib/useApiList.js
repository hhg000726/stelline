/* 목록 하나를 받아 오는 동안 칸이 거치는 상태.
 *
 * 여러 칸이 같은 길을 걷는다. 받아오는 중에는 빈칸(스켈레톤)을, 실패하면 안내 한 줄을
 * 보여 주고, 화면을 떠난 뒤에 도착한 값은 반영하지 않는다. 마지막 규칙을 화면마다 따로
 * 적으면 한 곳만 빠뜨려도 사라진 칸을 다시 그리려다 경고가 난다.
 *
 * 주소와 옵션은 화면마다 고정이라 예전처럼 한 번만 받아 온다.
 */
import { useEffect, useState } from "react";

import { api } from "./api";
import { toArray } from "./toArray";

export function useApiList(path, { options, errorLabel, select = toArray } = {}) {
  const [state, setState] = useState({ status: "loading", items: [] });

  useEffect(() => {
    let alive = true;
    api(path, options)
      .then((response) => response.json())
      .then((data) => {
        if (alive) setState({ status: "ready", items: select(data) });
      })
      .catch((error) => {
        console.error(errorLabel, error);
        if (alive) setState({ status: "error", items: [] });
      });
    return () => {
      alive = false;
    };
  }, []);

  return state;
}
