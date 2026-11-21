from setuptools import setup

setup(name="roboracer_f1tenth", version="0.1.0", packages=["roboracer_f1tenth"],
      data_files=[("share/ament_index/resource_index/packages", ["resource/roboracer_f1tenth"]),
                  ("share/roboracer_f1tenth", ["package.xml"]),
                  ("share/roboracer_f1tenth/launch", ["launch/f1tenth_twin.launch.py"])],
      install_requires=["setuptools"],
      zip_safe=True,
      description="f1tenth_system's own nodes against the RoboRacer twin (scensim roadmap 091 W20)",
      license="Apache-2.0",
      entry_points={"console_scripts": ["wall_follow = roboracer_f1tenth.wall_follow:main"]})
